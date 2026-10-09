"""Code-level checks on the LLM's answer.

A prompt can ask a model not to invent prices; it cannot guarantee it. These
checks are plain Python, so they behave the same way every time:

  1. check_numbers()  - every number in the answer must literally appear in
                        the passages the model was given. An invented or
                        "remembered" price fails this check.
  2. check_no_links() - the model must not write URLs itself; links are built
                        by our code from the list of 7 allowed pages.

What these checks do NOT catch: a real number attached to the wrong thing
(e.g. quoting the in-patient price for the out-patient program). That is
handled by the prompt rules and by keeping each number next to its label
during extraction.
"""

import re
import unicodedata

# A number, optionally with a currency sign in front. Thousands separators are
# removed before this runs, so "18,995" is already "18995" here.
_NUMBER = re.compile(r"(?P<currency>[$€£]\s?)?(?P<number>\d+(?:\.\d+)?)(?P<suffix>\s?(?:%|USD|usd))?")
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)


def _to_ascii_digits(text: str) -> str:
    """Convert digits from other scripts (e.g. Arabic-Indic ٣) to 0-9, so an
    Arabic answer is checked exactly like an English one."""
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch
                   for ch in text)


def _canonical(number: str) -> str:
    """One spelling per value: '06' -> '6', '5.0' -> '5', '18995' -> '18995'."""
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number.lstrip("0") or "0"


def _prepare(text: str) -> str:
    text = _to_ascii_digits(text)
    # Drop thousands separators: "18,995" -> "18995" (a comma between a digit
    # and exactly three digits). The price list writes "$18995" and the
    # package pages "$18,995" - both must count as the same number.
    return re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)


def extract_numbers(text: str) -> set[str]:
    """All numbers in a text, in canonical form."""
    return {_canonical(m.group("number")) for m in _NUMBER.finditer(_prepare(text))}


def _allowed_numbers(passages: list[dict]) -> set[str]:
    """Every number that appears in the passages. The section heading counts
    as evidence too (e.g. "Included in the Out-Patient Program ($18,995 USD)")."""
    allowed: set[str] = set()
    for passage in passages:
        allowed |= extract_numbers(f"{passage['page_title']} {passage['section']} {passage['text']}")
    return allowed


def _is_unsupported(match: re.Match, allowed: set[str]) -> bool:
    number = _canonical(match.group("number"))
    if number in allowed:
        return False
    # A bare single digit ("2 programs", "one of 3 options") is everyday
    # counting, not a quoted fact. But "$5" or "5%" is a claim -> checked.
    is_claim = bool(match.group("currency") or match.group("suffix"))
    return is_claim or len(number) > 1


def check_numbers(answer: str, passages: list[dict]) -> list[str]:
    """Return the numbers in `answer` that are NOT supported by the passages.
    An empty list means the answer passed.
    """
    allowed = _allowed_numbers(passages)
    return [match.group(0).strip() for match in _NUMBER.finditer(_prepare(answer))
            if _is_unsupported(match, allowed)]


MASK = "[a figure that is NOT on the PlacidWay pages]"


def mask_unsupported_numbers(text: str, passages: list[dict]) -> str:
    """Replace numbers in the VISITOR's message that the relevant page does
    not contain with a placeholder, before the answering model sees the message.

    This is the defence against "I heard it costs $50, confirm that": the
    model never sees "$50", so it can neither agree with it nor repeat it, and
    the placeholder tells it outright that the figure is not on the pages.

    A visitor's number is kept only if it appears on the page of the TOP
    passage (the page the question is about). Checking all passages is not
    enough: keyword search happily retrieves an unrelated page that merely
    contains "$50", and the model then starts talking about that page.
    """
    if passages:
        main_page = passages[0]["source_id"]
        passages = [p for p in passages if p["source_id"] == main_page]
    allowed = _allowed_numbers(passages)
    return _NUMBER.sub(lambda m: MASK if _is_unsupported(m, allowed) else m.group(0), _prepare(text))


def contains_figures(answer: str) -> bool:
    """True if the answer states a price or any multi-digit number. Used to
    enforce "an answer that quotes figures must cite the page they came from"."""
    return any(match.group("currency") or match.group("suffix") or len(match.group("number")) > 1
               for match in _NUMBER.finditer(_prepare(answer)))


def check_no_links(answer: str) -> bool:
    """True if the answer contains no URL."""
    return _URL.search(answer) is None
