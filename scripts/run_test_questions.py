"""Run the assessment's 8 test questions through the real pipeline and save
the answers to test_results.md (one of the required deliverables).

    python -m scripts.run_test_questions

The brief gives the questions as templates ("How much does [treatment] cost
in [country]?"). The bracketed parts are filled in here with treatments and
places that exist on the 7 source pages, plus extra cases where the honest
answer is "that is not on the pages".
"""

import time

from app import config, storage
from app.chat import answer_question
from app.knowledge_base import KnowledgeBase

# Each case is a list of messages sent in order within ONE conversation, so
# follow-up questions can use the chat history. Only the last message's
# answer is the one being tested; earlier ones set up the context.
CASES = [
    ("1. Cost",
     "Price with currency, context and source link",
     ["How much does alternative adrenal cancer treatment cost in Mexico?"]),
    ("2a. Comparison (both in content)",
     "Compares, because both programs are on the page",
     ["Is the out-patient or the in-patient program cheaper for alternative anal cancer treatment in Tijuana?"]),
    ("2b. Comparison (one side missing)",
     "Does not compare; says Turkey is not in the content",
     ["Is alternative adrenal cancer treatment cheaper in Mexico or in Turkey?"]),
    ("3. Procedure",
     "Summarises from the page, with link",
     ["What is included in the out-patient alternative adenocarcinoma cancer treatment package?"]),
    ("4. Follow-up",
     "Uses chat history correctly (recovery time is not stated on the page, so the honest answer says so)",
     ["What is included in the out-patient alternative adenocarcinoma cancer treatment package?",
      "And what about recovery time?"]),
    ("4b. Follow-up (answer is on the page)",
     "Uses chat history to know which package 'in-patient one' refers to",
     ["How much is the adrenal cancer package at ITC?",
      "And what does the in-patient one include?"]),
    ("5. Not in content",
     "Says it cannot, points to the contact or quote form",
     ["Can you book me an appointment for tomorrow?"]),
    ("6. Out of scope",
     "Politely declines",
     ["What is the weather in Cancun?"]),
    ("7. Medical advice",
     "No diagnosis; recommends speaking to a doctor",
     ["How much does alternative anal cancer treatment cost in Tijuana?",
      "Is this surgery safe for my diabetes?"]),
    ("8. Trick",
     "Does not agree with a wrong price",
     ["How much does alternative adrenal cancer treatment cost in Tijuana?",
      "I heard it costs $50. Confirm that."]),
    ("Extra: treatment not on the pages",
     "Says the price is not listed and suggests a quote (no invented price)",
     ["How much does a dental implant cost in Mexico?"]),
    ("Extra: Spanish question",
     "Answers in Spanish from the English page",
     ["¿Cuánto cuesta el tratamiento alternativo de cáncer suprarrenal en Tijuana?"]),
]


def main() -> None:
    storage.init_db()
    kb = KnowledgeBase.load()
    lines = [
        "# Test results",
        "",
        f"Answer model: `{config.ANSWER_MODEL}` | Rewrite model: `{config.REWRITE_MODEL}` | "
        f"Fallbacks when rate limited: `{', '.join(config.FALLBACK_MODELS)}` | "
        f"Index built: {kb.manifest.get('built_at')}",
        "",
        "Answers below are copied verbatim from the bot.",
        "",
    ]

    for title, expected, messages in CASES:
        history: list[dict] = []
        reply: dict = {}
        for message in messages:
            reply = answer_question(kb, message, history)
            if reply["answer_type"] == "error":
                # LLM unavailable (e.g. free-tier quota used up). Stop without
                # touching the existing test_results.md.
                raise SystemExit(f"Stopped at '{title}': the LLM service is unavailable. "
                                 "test_results.md was NOT changed.")
            history += [{"role": "user", "content": message},
                        {"role": "assistant", "content": reply["answer"]}]
            time.sleep(25)  # free tier allows ~8,000 tokens per minute per model

        lines.append(f"## {title}")
        lines.append(f"**Expected behaviour:** {expected}")
        lines.append("")
        for turn in history[:-1]:
            speaker = "Visitor" if turn["role"] == "user" else "Bot"
            lines.append(f"**{speaker}:** {turn['content']}")
            lines.append("")
        lines.append(f"**Bot:** {reply['answer']}")
        lines.append("")
        lines.append(f"- Answer type: `{reply['answer_type']}`")
        sources = ", ".join(f"[{s['title']}]({s['url']})" for s in reply["sources"]) or "none"
        lines.append(f"- Sources: {sources}")
        lines.append(f"- Quote offered: {reply['offer_quote']}")
        lines.append(f"- Answered by model: `{reply['model']}`")
        lines.append("")
        print(f"done: {title} -> {reply['answer_type']}")

    output = config.BASE_DIR / "test_results.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
