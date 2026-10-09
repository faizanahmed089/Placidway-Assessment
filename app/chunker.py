"""Step 3 of ingestion: group text blocks into retrievable passages ("chunks").

Chunking strategy, in plain words:
  * A new chunk starts at every main heading (h2). The page authors already
    split the page by topic ("Cost of ...", "Included in ...", "FAQs"), so
    their headings are better boundaries than any fixed character count.
  * If one section is longer than MAX_CHUNK_CHARS it is split between lines,
    never in the middle of a line - so a table row or a list item (which is
    where prices live) is never cut in half.
  * A sub-heading or a question is never left dangling at the end of a chunk;
    it moves to the next chunk together with the text that belongs to it.
  * Every chunk stores its page title, section heading and URL. Three of the
    source pages are near-identical packages (adenocarcinoma / adrenal / anal
    cancer); the page title inside each chunk is what keeps them apart.
"""

import re

from app import config


def _split_long_line(line: str, limit: int) -> list[str]:
    """Break a single over-long paragraph at sentence ends."""
    if len(line) <= limit:
        return [line]
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", line):
        if current and len(current) + len(sentence) + 1 > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _is_lead_in(line: str) -> bool:
    """True for a line that introduces the NEXT line: a sub-heading (we mark
    those with '### ') or a FAQ question."""
    return line.startswith("### ") or line.endswith("?")


def _pack_lines(lines: list[str], limit: int) -> list[list[str]]:
    """Greedily pack lines into groups of at most `limit` characters."""
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0
    for line in lines:
        if current and size + len(line) + 1 > limit:
            # Do not strand a heading/question at the bottom of a chunk:
            # carry it over to the chunk that holds its answer.
            carried = []
            while current and _is_lead_in(current[-1]):
                carried.insert(0, current.pop())
            if current:
                groups.append(current)
            current = carried
            size = sum(len(c) + 1 for c in current)
        current.append(line)
        size += len(line) + 1
    if current:
        groups.append(current)
    return groups


def chunk_page(source: dict, page: dict) -> list[dict]:
    """Turn one extracted page into a list of chunk dicts.

    `source` is an entry from config.SOURCES, `page` is extract_page() output.
    """
    # --- 1. Group blocks into sections, one per h2 heading.
    sections: list[dict] = []
    current = {"heading": "Introduction", "lines": []}
    for block in page["blocks"]:
        if block["kind"] == "heading" and block["level"] <= 2:
            sections.append(current)
            current = {"heading": block["text"], "lines": []}
        elif block["kind"] == "heading":
            current["lines"].append(f"### {block['text']}")  # h3/h4 stay inline
        else:
            current["lines"].extend(_split_long_line(block["text"], config.MAX_CHUNK_CHARS))
    sections.append(current)

    # --- 2. Split each section into chunks of bounded size.
    chunks: list[dict] = []
    for section in sections:
        # A section with only sub-headings and no text (e.g. an empty
        # "Location" map block) has nothing to answer from - skip it.
        if not any(not line.startswith("### ") for line in section["lines"]):
            continue
        for group in _pack_lines(section["lines"], config.MAX_CHUNK_CHARS):
            body = "\n".join(group)
            chunks.append({
                "id": f"{source['id']}-{len(chunks):03d}",
                "source_id": source["id"],
                "url": source["url"],
                "page_type": source["page_type"],
                "page_title": page["title"],
                "section": section["heading"],
                "text": body,
            })
    return chunks


def chunk_search_text(chunk: dict) -> str:
    """The text that is embedded and keyword-indexed for a chunk.

    Page title and section heading are prepended so that a chunk saying only
    "Out-Patient Program | 3 Weeks | $18,995" is still findable by a question
    that mentions "adrenal cancer" (which appears only in the page title).
    """
    return f"{chunk['page_title']}\n{chunk['section']}\n{chunk['text']}"
