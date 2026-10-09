"""Unit tests for the parts that must never be wrong: the number check, the
link check, the table extraction and the chunker. They need no network and
no API key.  Run with:  pytest
"""

from app import guardrails
from app.chunker import chunk_page
from app.extractor import extract_page

PASSAGES = [{
    "source_id": "package-adrenal",
    "page_title": "Alternative Adrenal Cancer Treatment Package in Tijuana, Mexico by ITC",
    "section": "Included in the Out-Patient Program ($18,995 USD)",
    "text": "Program Type: In-Patient Program | Duration: 3 Weeks | Total Cost (USD): $30,000\n"
            "Procedure: Breast Cancer | Price in USD: $18995\n"
            "Blood transfusions if required (Approx. $462 per pint). Open 24/7.",
}]


# ----------------------------- number check ------------------------------
def test_price_copied_from_passage_passes():
    assert guardrails.check_numbers("The out-patient program costs $18,995 USD.", PASSAGES) == []


def test_comma_and_no_comma_spellings_are_the_same_number():
    # Passage says "$18995" and "$18,995"; either spelling in the answer is fine.
    assert guardrails.check_numbers("It is $18995, or $30,000 in-patient.", PASSAGES) == []


def test_invented_price_is_caught():
    assert guardrails.check_numbers("It costs $50.", PASSAGES) == ["$50"]


def test_user_supplied_wrong_price_is_caught_even_inside_a_denial():
    # "I can't confirm $50" still repeats an unsupported figure -> rejected,
    # which triggers the retry that asks the model to drop it.
    assert guardrails.check_numbers("I can't confirm $50; the page says $18,995.", PASSAGES) == ["$50"]


def test_bare_single_digit_is_allowed_but_single_digit_price_is_not():
    assert guardrails.check_numbers("There are 2 programs.", PASSAGES) == []
    assert guardrails.check_numbers("It costs $2.", PASSAGES) == ["$2"]


def test_european_number_format_is_caught():
    # "18.995" is a different number from "18,995" -> must not slip through.
    assert guardrails.check_numbers("Cuesta $18.995 USD.", PASSAGES) != []


def test_arabic_digits_are_checked_like_ascii_digits():
    assert guardrails.check_numbers("السعر ١٨٩٩٥ دولار", PASSAGES) == []
    assert guardrails.check_numbers("السعر ٥٠٠٠ دولار", PASSAGES) != []


def test_wrong_price_from_visitor_is_masked_but_real_price_is_kept():
    masked = guardrails.mask_unsupported_numbers("I heard it costs $50. Confirm that.", PASSAGES)
    assert "50" not in masked and guardrails.MASK in masked
    kept = guardrails.mask_unsupported_numbers("Is it really $18,995 for 3 weeks?", PASSAGES)
    assert guardrails.MASK not in kept and "18995" in kept


def test_visitor_figure_found_only_on_an_unrelated_page_is_still_masked():
    # Keyword search also returned a price-comparison passage containing "$50".
    # The question is about the adrenal package (top passage), so "$50" is hidden.
    other_page = {"source_id": "price-comparison", "page_title": "Alternative Medicine Cost Abroad",
                  "section": "Cost Breakdown", "text": "Initial Holistic Consultation | Low (USD): $50"}
    masked = guardrails.mask_unsupported_numbers("Does it cost $50?", PASSAGES + [other_page])
    assert "50" not in masked and guardrails.MASK in masked


def test_claimed_prices_are_removed_from_the_search_query():
    stripped = guardrails.strip_price_figures("Does the 3 week adrenal program cost $50 or 500 USD?")
    assert "50" not in stripped and "500" not in stripped
    assert "3 week adrenal program" in stripped  # ordinary numbers stay


def test_contains_figures_detects_prices_but_not_plain_counting():
    assert guardrails.contains_figures("It costs $18,995 USD.") is True
    assert guardrails.contains_figures("There are 2 programs.") is False
    assert guardrails.contains_figures("I can't book appointments.") is False


# ------------------------------ keyword search ------------------------------
def test_word_forms_share_one_token():
    from app.knowledge_base import tokenize
    assert tokenize("include") == tokenize("Included") == tokenize("includes") == tokenize("including")
    assert tokenize("$18,995") == tokenize("18995")


# ---------------------------- medical disclaimer ----------------------------
def test_personal_medical_question_always_gets_the_doctor_note():
    from app.chat import _show_disclaimer
    medical = {"answer_type": "medical", "medical_disclaimer": False}
    # Shown even if the model forgot the flag and even if it was shown before.
    assert _show_disclaimer(medical, already_shown=True) is True


def test_ordinary_treatment_answer_shows_the_note_only_once():
    from app.chat import _show_disclaimer
    answered = {"answer_type": "answered", "medical_disclaimer": True}
    assert _show_disclaimer(answered, already_shown=False) is True
    assert _show_disclaimer(answered, already_shown=True) is False
    assert _show_disclaimer({"answer_type": "out_of_scope", "medical_disclaimer": True}, False) is False


# ------------------------------- link check -------------------------------
def test_links_are_rejected():
    assert guardrails.check_no_links("See the price list page.") is True
    assert guardrails.check_no_links("See https://example.com/prices") is False
    assert guardrails.check_no_links("Visit www.example.com") is False


# --------------------------- extraction + chunking ---------------------------
SAMPLE_HTML = """
<html><body>
  <nav>Home | Dentistry | Fertility</nav>
  <div class="pack-title-price-header">
    <h1>Sample Package</h1>
    <div class="actual-price"><span>$1,000</span> <span>Price starting from</span></div>
  </div>
  <main class="article-dt-desc">
    <!-- hidden note: prices range between $1 - $2 -->
    <h2>Cost</h2>
    <table>
      <thead><tr><th>Program</th><th>Price</th><th>Actions</th></tr></thead>
      <tbody>
        <tr><td>Out-Patient</td><td>$1,000</td><td><button>Chat with Center</button></td></tr>
        <tr><td></td><td>$999</td><td><button>Chat with Center</button></td></tr>
      </tbody>
    </table>
    <h2>Location</h2>
    <script>var price = 777;</script>
  </main>
  <section class="related-centers-sec"><h3>Some Other Clinic - $5</h3></section>
  <footer>Footer text</footer>
</body></html>
"""
SOURCE = {"id": "sample", "url": "https://example.com/sample", "page_type": "Treatment package"}


def _sample_text() -> str:
    chunks = chunk_page(SOURCE, extract_page(SAMPLE_HTML))
    return "\n".join(chunk["text"] for chunk in chunks)


def test_table_rows_keep_their_column_labels():
    assert "Program: Out-Patient | Price: $1,000" in _sample_text()


def test_noise_is_removed():
    text = _sample_text()
    assert "Chat with Center" not in text   # action buttons
    assert "777" not in text                # scripts
    assert "$1 - $2" not in text            # HTML comments
    assert "Other Clinic" not in text       # related-clinic carousel outside <main>
    assert "Dentistry" not in text          # site navigation
    assert "Footer" not in text


def test_price_without_a_label_is_dropped():
    # The second table row has a price but no program name.
    assert "$999" not in _sample_text()


def test_header_price_keeps_its_starting_from_context():
    assert "$1,000 Price starting from" in _sample_text()


def test_chunks_carry_source_metadata_and_empty_sections_are_skipped():
    chunks = chunk_page(SOURCE, extract_page(SAMPLE_HTML))
    assert all(c["url"] == SOURCE["url"] and c["page_title"] == "Sample Package" for c in chunks)
    assert "Location" not in [c["section"] for c in chunks]  # heading with no content
