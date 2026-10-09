"""The question-answering pipeline. One function, `answer_question()`, runs
every step for one visitor message:

    1. REWRITE   follow-up / non-English message -> standalone English query
    2. RETRIEVE  hybrid search over the 7 pages
    3. GATE      if nothing is similar enough, hand the LLM NO passages
    4. GENERATE  LLM writes a JSON answer using only the passages
    5. VERIFY    Python checks numbers, links and citations (one retry)
    6. RESPOND   attach source links, quote offer, disclaimer flag; log gaps

The LLM never produces a URL: it returns passage NUMBERS and this module
turns them into links, so a cited link can only be one of the 7 source pages.
"""

import logging
import re

from app import config, guardrails, storage
from app.knowledge_base import KnowledgeBase
from app.llm import LLMError, ask_json
from app.prompts import (ANSWER_SYSTEM, REWRITE_SYSTEM, build_answer_prompt,
                         build_rewrite_prompt)

log = logging.getLogger(__name__)

ANSWER_TYPES = {"answered", "not_found", "medical", "cannot_do", "out_of_scope", "smalltalk"}
# Answer types that may state facts from the pages, and so may carry sources.
# "not_found" is included for partial answers such as "Mexico costs X, but
# Turkey is not on the pages" - the X still needs its source link.
TYPES_WITH_SOURCES = {"answered", "medical", "not_found"}

# Used when the LLM's answer fails verification twice. Deliberately fixed
# text: when we cannot trust the generated answer, we do not show any of it.
FALLBACK_ANSWER = (
    "I'm sorry, I couldn't find a reliable answer to that in the PlacidWay pages "
    "I have access to. For accurate, personalised details, please request a free "
    "quote from PlacidWay and their team will get back to you."
)
SERVICE_ERROR_ANSWER = (
    "Sorry, I'm having trouble reaching the answer service right now. "
    "Please try again in a moment."
)


def _trim_history(history: list[dict]) -> list[dict]:
    """Keep only the most recent turns, and cap their length, so a long chat
    cannot blow up the prompt size (and the free-tier token budget)."""
    recent = history[-config.MAX_HISTORY_TURNS * 2:]
    return [{"role": turn["role"], "content": turn["content"][:1000]} for turn in recent]


def _rewrite(message: str, history: list[dict]) -> tuple[str, str, str]:
    """Step 1. Returns (standalone English search query, the same question in
    other words, visitor's language)."""
    reply = ask_json(config.REWRITE_MODEL, REWRITE_SYSTEM,
                     build_rewrite_prompt(history, message), max_tokens=800)
    query = reply.get("search_query")
    language = reply.get("language")
    # If the small model returns something odd, fall back to the raw message
    # rather than failing the whole request.
    if not isinstance(query, str) or not query.strip():
        query = message
    # `language` is pasted into the answer prompt, so it is restricted to a
    # short run of letters - the model's output is never trusted as instructions.
    language = re.sub(r"[^A-Za-z ]", "", language)[:30].strip() if isinstance(language, str) else ""
    if not language:
        language = "the same language as the visitor message"
    alternative = reply.get("alternative_query")
    alternative = alternative.strip()[: config.MAX_MESSAGE_CHARS] if isinstance(alternative, str) else ""
    return query.strip()[: config.MAX_MESSAGE_CHARS], alternative, language


def _validate(reply: dict, passages: list[dict]) -> tuple[dict | None, str]:
    """Step 5. Check one LLM reply.

    Returns (clean_reply, "") if it is acceptable, or (None, reason) if it must
    be rejected. `reason` is written so it can be sent back to the model.
    """
    answer_type = reply.get("answer_type")
    answer = reply.get("answer")
    if answer_type not in ANSWER_TYPES or not isinstance(answer, str) or not answer.strip():
        return None, "The JSON did not follow the required format."

    # Keep only citations that point at a passage we actually supplied.
    cited = reply.get("sources")
    cited = cited if isinstance(cited, list) else []
    valid = sorted({n for n in cited if isinstance(n, int) and not isinstance(n, bool)
                    and 1 <= n <= len(passages)})

    # A factual answer with no source is not allowed: "each answer cites its source".
    if answer_type == "answered" and not valid:
        return None, ("You gave a factual answer without listing any passage in \"sources\". "
                      "If the PASSAGES do not contain the answer, use answer_type \"not_found\".")

    # Same rule for any reply that quotes a figure, whatever its type.
    if guardrails.contains_figures(answer) and not valid:
        return None, ("Your answer quoted a price or number but \"sources\" was empty. "
                      "List the passage numbers the figures came from.")

    # Every number must come from the passages.
    unsupported = guardrails.check_numbers(answer, passages)
    if unsupported:
        return None, (f"Your answer contained numbers that are not in the PASSAGES: "
                      f"{', '.join(unsupported)}. Rewrite the answer without them. If the "
                      f"visitor mentioned such a number, refer to it in words (\"that price\") "
                      f"instead of writing it, and copy prices exactly as written in the PASSAGES.")

    if not guardrails.check_no_links(answer):
        return None, "Your answer contained a URL. Do not write links in the answer."

    return {
        "answer_type": answer_type,
        "answer": answer.strip(),
        "sources": valid if answer_type in TYPES_WITH_SOURCES else [],
        "offer_quote": bool(reply.get("offer_quote")) or answer_type in ("not_found", "cannot_do"),
        "medical_disclaimer": bool(reply.get("medical_disclaimer")),
        "model": reply.get("_model", ""),
    }, ""


def _generate(passages: list[dict], query: str, message: str, language: str) -> dict | None:
    """Steps 4 + 5. Ask the LLM; if verification rejects the answer, tell the
    model why and try exactly once more. Returns None if both attempts fail."""
    system_prompt = ANSWER_SYSTEM.replace("{language}", language)
    # Hide visitor-supplied figures that the pages do not contain (see guardrails).
    query = guardrails.mask_unsupported_numbers(query, passages)
    message = guardrails.mask_unsupported_numbers(message, passages)
    correction = ""
    for attempt in (1, 2):
        reply = ask_json(config.ANSWER_MODEL, system_prompt,
                         build_answer_prompt(passages, query, message, correction))
        clean, reason = _validate(reply, passages)
        if clean is not None:
            return clean
        log.warning("Answer rejected (attempt %s): %s", attempt, reason)
        correction = reason
    return None


def _source_links(passages: list[dict], cited_numbers: list[int]) -> list[dict]:
    """Turn cited passage numbers into a de-duplicated list of page links."""
    links, seen = [], set()
    for number in cited_numbers:
        passage = passages[number - 1]
        if passage["url"] not in seen:
            seen.add(passage["url"])
            links.append({"title": passage["page_title"], "url": passage["url"],
                          "page_type": passage["page_type"]})
    return links


def _response(answer: str, answer_type: str, sources=(), offer_quote=False,
              show_disclaimer=False, model: str = "") -> dict:
    return {
        "model": model,  # which LLM wrote the answer (the fallback may have been used)
        "answer": answer,
        "answer_type": answer_type,
        "sources": list(sources),
        "offer_quote": offer_quote,
        "show_disclaimer": show_disclaimer,
        "quote_url": config.QUOTE_URL,
    }


def answer_question(kb: KnowledgeBase, message: str, history: list[dict],
                    disclaimer_shown: bool = False) -> dict:
    """Run the whole pipeline for one visitor message and return the reply
    payload that the API sends to the browser."""
    message = message.strip()[: config.MAX_MESSAGE_CHARS]
    history = _trim_history(history)
    query, best_score = message, 0.0

    try:
        # 1. Rewrite.
        query, alternative, language = _rewrite(message, history)

        # 2. Retrieve (with both wordings of the question).
        passages, best_score = kb.search(query, alternative)

        # 3. Relevance gate. Below the threshold the question is not about
        # anything on the pages, so the LLM gets no passages at all - it can
        # then only decline, greet or redirect; it has nothing to "answer" from.
        if best_score < config.MIN_SIMILARITY:
            passages = []

        # 4 + 5. Generate and verify.
        result = _generate(passages, query, message, language)
    except LLMError as error:
        log.error("LLM failure: %s", error)
        storage.log_unanswered(message, query, "llm_error", best_score)
        return _response(SERVICE_ERROR_ANSWER, "error")

    # Verification failed twice -> safe fixed reply, and record it for review.
    if result is None:
        storage.log_unanswered(message, query, "guardrail_blocked", best_score)
        return _response(FALLBACK_ANSWER, "not_found", offer_quote=True)

    # Content-gap log: on-topic questions the pages could not answer.
    if result["answer_type"] == "not_found":
        storage.log_unanswered(message, query, "not_found", best_score)

    # 6. Respond. The disclaimer is shown once per conversation, not on every
    # answer: the browser tells us whether it has already displayed it.
    return _response(
        answer=result["answer"],
        answer_type=result["answer_type"],
        sources=_source_links(passages, result["sources"]),
        offer_quote=result["offer_quote"],
        show_disclaimer=result["medical_disclaimer"] and not disclaimer_shown
        and result["answer_type"] in ("answered", "medical"),
        model=result["model"],
    )
