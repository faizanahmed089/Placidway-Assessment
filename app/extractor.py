"""Step 2 of ingestion: turn raw HTML into clean, ordered text blocks.

A PlacidWay page is 300-900 KB of HTML but only ~15-40 KB of it is real
content. The rest is navigation, footers, pop-ups, "related" carousels that
advertise OTHER clinics, and widgets. Feeding that noise to a search index
makes retrieval worse and could make the bot talk about clinics that are not
part of the knowledge base, so we cut it out here.

Output of this module is a list of "blocks" in reading order:
    {"kind": "heading", "level": 2, "text": "Cost of ..."}
    {"kind": "text", "text": "The Out-patient program is ..."}
The chunker (chunker.py) then groups these blocks into passages.
"""

import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# On every source page the real content sits in exactly two containers:
#   1. the title/price header at the top of the page
#   2. the <main class="article-dt-desc"> body
# Everything outside them (site header, footer, related clinics, chat widget)
# is ignored simply because we never look at it.
HEADER_SELECTOR = "div.pack-title-price-header"
MAIN_SELECTOR = "main.article-dt-desc"

# Tags that never hold readable content.
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "img", "form",
              "button", "select", "option", "input", "textarea", "label", "nav"]

# Noise that lives INSIDE the two content containers.
NOISE_SELECTORS = [
    "[class*=popup]",            # "request a video call" pop-up (incl. a 100-item time-zone list)
    "[class*=modal]",
    ".table-of-contents",        # links that only repeat the headings
    ".social-count",             # view / like counters ("1232", "0", "0")
    ".viewcount-social-icon",    # share buttons
    ".star-rating",              # star icons (the numeric rating text is kept)
    "a.button",                  # "Read More" / "Contact ..." call-to-action buttons
    '[style*="display: none"]',  # elements the page itself hides from visitors
    '[style*="display:none"]',
]

# Tags that start a new line of content. Anything not listed here (span, a,
# strong, em ...) is "inline" and stays inside its parent's sentence.
BLOCK_TAGS = {"div", "p", "section", "article", "main", "header", "footer", "aside",
              "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th",
              "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "dl", "dt", "dd",
              "figure", "figcaption", "details", "summary"}

HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 4, "h6": 4}

# Table columns that only contain buttons ("Chat with Center", "Quote").
ACTION_COLUMNS = {"action", "actions"}

# Link/button captions that are calls to action, not information.
CTA_PHRASES = {"read more", "load more", "get a free quote", "get your quote now!",
               "view center reviews", "write a review", "chat with center", "quote"}


def clean_text(text: str) -> str:
    """Collapse whitespace and fix the ' .' / ' ,' gaps left by inline tags."""
    text = text.replace("\xa0", " ")           # non-breaking spaces
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text


def _text_of(element: Tag) -> str:
    return clean_text(element.get_text(" ", strip=True))


def _remove_noise(root: Tag) -> None:
    """Delete noise elements from the parsed tree, in place."""
    # HTML comments are invisible to visitors but BeautifulSoup returns them as
    # text. The price-list page has a commented-out sentence containing a price
    # range - if a human cannot see it on the page, the bot must not quote it.
    for comment in root.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()
    for tag in root.find_all(NOISE_TAGS):
        tag.decompose()
    for selector in NOISE_SELECTORS:
        for tag in root.select(selector):
            tag.decompose()

    # "Related Experiences:" is a list of links to OTHER pages (dental implants,
    # eyelid surgery ...). We must not answer from pages outside the 7 sources.
    for heading in root.find_all(["h2", "h3", "h4"]):
        if _text_of(heading).lower().startswith("related experiences"):
            (heading.parent or heading).decompose()


def _simplify_video_cards(root: Tag, soup: BeautifulSoup) -> None:
    """The videos page lists ~120 cards, each a title plus repeated boilerplate
    (category, clinic name, city). Replace each card with one short line so the
    list becomes compact, searchable text instead of 120 tiny sections."""
    cards = root.select(".related-videos-card")
    if cards:
        # Give the list its own heading so it is not filed under the section
        # that happens to come before it ("About ...").
        heading = soup.new_tag("h2")
        heading.string = "Videos listed on this page"
        cards[0].insert_before(heading)
    for card in cards:
        title = card.select_one(".title")
        if title is None:
            card.decompose()
            continue
        line = soup.new_tag("p")
        line.string = f"- Video: {_text_of(title)}"
        card.replace_with(line)


def _cell_text(cell: Tag) -> str:
    """Text of one table cell. Lists inside a cell are joined with '; ' so
    'Breast Cancer; Prostate Cancer' does not collapse into one long phrase."""
    items = cell.find_all("li")
    if items:
        return "; ".join(t for t in (_text_of(li) for li in items) if t)
    return _text_of(cell)


def _table_to_lines(table: Tag) -> list[str]:
    """Convert a table into one self-describing line per row, e.g.
        'Program Type: Out-Patient Program | Duration: 3 Weeks | Total Cost (USD): $18,995'
    Repeating the column name beside every value means a row still makes sense
    when it is read alone inside a chunk - a price never loses its label."""
    rows = table.find_all("tr")
    if not rows:
        return []

    # Header row = the first row, if it is made of <th> cells.
    headers: list[str] = []
    first_cells = rows[0].find_all(["th", "td"])
    if first_cells and all(c.name == "th" for c in first_cells):
        headers = [_text_of(c) for c in first_cells]
        rows = rows[1:]

    lines = []
    for row in rows:
        parts = []
        for position, cell in enumerate(row.find_all(["td", "th"])):
            header = headers[position] if position < len(headers) else ""
            if header.lower() in ACTION_COLUMNS:
                continue
            value = _cell_text(cell)
            if not value:
                continue
            parts.append(f"{header}: {value}" if header else value)
        # A row with a single value has lost its meaning (e.g. the price list
        # has one row with a price but NO procedure name). A price without a
        # label is exactly what the bot must not repeat, so we drop such rows.
        if len(parts) >= 2:
            lines.append(" | ".join(parts))
    return lines


def _has_block_child(element: Tag) -> bool:
    return any(isinstance(child, Tag) and child.name in BLOCK_TAGS
               for child in element.descendants)


def _walk(element: Tag, blocks: list[dict]) -> None:
    """Depth-first walk that emits blocks in reading order.

    Rule: an element that contains no block-level children is a "leaf" and
    becomes one text block. Otherwise we go one level deeper. Headings, list
    items and tables get their own handling so their structure is preserved.
    """
    for child in element.children:
        # Loose text sitting directly inside a container.
        if isinstance(child, NavigableString):
            text = clean_text(str(child))
            if text:
                blocks.append({"kind": "text", "text": text})
            continue
        if not isinstance(child, Tag):
            continue

        if child.name in HEADING_TAGS:
            text = _text_of(child)
            if text:
                blocks.append({"kind": "heading", "level": HEADING_TAGS[child.name], "text": text})
        elif child.name == "table":
            for line in _table_to_lines(child):
                blocks.append({"kind": "text", "text": line})
        elif child.name == "li" and not child.find(["ul", "ol", "table"]):
            text = _text_of(child)
            if text:
                blocks.append({"kind": "text", "text": f"- {text}"})
        elif child.name in BLOCK_TAGS and _has_block_child(child):
            _walk(child, blocks)
        else:
            text = _text_of(child)
            if text:
                blocks.append({"kind": "text", "text": text})


def _is_junk(block: dict) -> bool:
    """Drop blocks that carry no information on their own."""
    text = block["text"]
    if block["kind"] == "heading":
        return False
    if text.lstrip("- ").lower() in CTA_PHRASES:
        return True
    # Pure symbols (star icons, separators) are decoration, not content.
    return not re.search(r"[A-Za-z0-9]", text)


def extract_page(html: str) -> dict:
    """Parse one page. Returns {"title": str, "blocks": [...]}.

    Raises ValueError if the expected containers are missing - that means the
    site layout changed and the extractor needs attention, which is better
    than silently indexing an empty page.
    """
    soup = BeautifulSoup(html, "html.parser")

    header = soup.select_one(HEADER_SELECTOR)
    main = soup.select_one(MAIN_SELECTOR)
    if main is None:
        raise ValueError(f"Content container '{MAIN_SELECTOR}' not found")

    h1 = soup.find("h1")
    title = _text_of(h1) if h1 else _text_of(soup.title) if soup.title else "Untitled page"

    blocks: list[dict] = []

    # --- 1. Header: location, dates, reviewer and the "Price starting from" box.
    # We flatten it into ONE "Overview" section. Its small sub-headings (e.g.
    # "Medical Center Reviews") become plain lines, otherwise the headline
    # price would end up filed under a "Reviews" heading.
    if header is not None:
        _remove_noise(header)
        header_blocks: list[dict] = []
        _walk(header, header_blocks)
        blocks.append({"kind": "heading", "level": 2, "text": "Overview"})
        for block in header_blocks:
            if block["text"] != title:  # the <h1> itself is already the page title
                blocks.append({"kind": "text", "text": block["text"]})

    # --- 2. Main body.
    _remove_noise(main)
    _simplify_video_cards(main, soup)
    _walk(main, blocks)

    blocks = [b for b in blocks if not _is_junk(b)]
    return {"title": title, "blocks": blocks}
