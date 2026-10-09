"""Streamlit front end, used for the public demo on Streamlit Community Cloud.

It is a thin user interface over the SAME pipeline the FastAPI server uses
(`app.chat.answer_question`). Nothing about ingestion, retrieval, prompts or
guardrails is duplicated here - this file only draws the chat and calls it.

Run locally with:
    streamlit run streamlit_app.py
"""

import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import streamlit as st

# --------------------------------------------------------------------------
# Secrets. On Streamlit Cloud, secrets are entered in the app settings and
# exposed through st.secrets. Our code reads plain environment variables
# (app/config.py), so copy them across BEFORE importing anything from app/.
# Locally there is no secrets file and the values come from .env instead.
# --------------------------------------------------------------------------
try:
    for _name, _value in st.secrets.items():
        if isinstance(_value, str):
            os.environ[_name] = _value.strip()
except Exception:  # noqa: BLE001 - no secrets file when running locally
    pass

from app import config, storage  # noqa: E402 - must come after the secrets step

# app/config.py reads the environment only once, when it is first imported.
# Streamlit keeps the Python process alive between runs, so if the secrets
# were added or changed AFTER the app first started, config would still hold
# the old (empty) values. Re-apply them on every run to stay in sync.
config.GROQ_API_KEY = os.environ.get("GROQ_API_KEY", config.GROQ_API_KEY)
config.ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", config.ADMIN_TOKEN)
from app.chat import answer_question  # noqa: E402
from app.ingest import run_ingest  # noqa: E402
from app.knowledge_base import KnowledgeBase  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

st.set_page_config(page_title="PlacidWay Knowledge Chatbot", page_icon="💬")

DISCLAIMER = ("This is general information from PlacidWay's website, not medical advice. "
              "Please consult a qualified doctor about your own situation.")
EXAMPLES = [
    "How much does alternative adrenal cancer treatment cost in Tijuana?",
    "What is included in the in-patient adenocarcinoma cancer treatment program?",
    "How much does acupuncture cost abroad?",
    "¿Cuánto cuesta el tratamiento alternativo de cáncer anal en Tijuana?",
]


# --------------------------------------------------------------------------
# Knowledge base. st.cache_resource keeps ONE copy in memory for all visitors.
# The `ttl` makes the cached copy expire after AUTO_REFRESH_HOURS, so the next
# visitor after that triggers a re-crawl: this is the automatic refresh.
# --------------------------------------------------------------------------
@st.cache_resource(ttl=config.AUTO_REFRESH_HOURS * 3600 or None, show_spinner="Loading the knowledge base...")
def load_knowledge_base() -> KnowledgeBase:
    storage.init_db()
    if _index_is_stale():
        try:
            log.info("Refresh check: %s", run_ingest())
        except Exception:  # noqa: BLE001 - crawl failed: keep serving the index we have
            log.exception("Refresh failed; using the existing index")
    return KnowledgeBase.load()


def _index_is_stale() -> bool:
    """True if the pages were last checked more than AUTO_REFRESH_HOURS ago
    (or never). Avoids re-crawling PlacidWay on every app restart."""
    if config.AUTO_REFRESH_HOURS <= 0:
        return not config.CHUNKS_FILE.exists()
    try:
        manifest = json.loads(config.MANIFEST_FILE.read_text(encoding="utf-8"))
        last_checked = datetime.fromisoformat(manifest["last_checked"])
    except (OSError, KeyError, ValueError):
        return True
    age = datetime.now(timezone.utc) - last_checked
    return age > timedelta(hours=config.AUTO_REFRESH_HOURS)


def show_text(text: str) -> None:
    """Display text from the bot or the visitor. Streamlit treats $...$ as a
    maths formula, which would mangle prices like "$18,995 ... $30,000", so
    dollar signs are escaped. HTML is not rendered (Streamlit's default)."""
    st.markdown(text.replace("$", "\\$"))


def show_bot_extras(message: dict, index: int) -> None:
    """Source links, the one-time disclaimer and the quote form under an answer."""
    if message.get("sources"):
        st.caption("Source" if len(message["sources"]) == 1 else "Sources")
        for source in message["sources"]:
            st.markdown(f"- [{source['title']} ({source['page_type']})]({source['url']})")

    if message.get("show_disclaimer"):
        st.caption(DISCLAIMER)

    if message.get("offer_quote"):
        with st.expander("Want exact details? Request a free quote"):
            st.markdown(f"[Open PlacidWay's free quote form]({message['quote_url']})")
            st.write("Or leave your details and PlacidWay can contact you:")
            # `index` keeps the form's key unique when several answers offer a quote.
            with st.form(key=f"lead-{index}"):
                name = st.text_input("Your name", max_chars=100)
                email = st.text_input("Email", max_chars=200)
                if st.form_submit_button("Send"):
                    if name.strip() and "@" in email and "." in email.split("@")[-1]:
                        storage.save_lead(name.strip(), email.strip(), message.get("question", ""))
                        st.success("Thank you - your details were saved.")
                    else:
                        st.error("Please enter your name and a valid email address.")


def handle_question(kb: KnowledgeBase, question: str) -> None:
    """Send one question through the pipeline and store both turns."""
    messages = st.session_state.messages
    # Follow-ups need the earlier turns; the pipeline trims them to the last few.
    history = [{"role": m["role"], "content": m["content"]} for m in messages]
    disclaimer_shown = any(m.get("show_disclaimer") for m in messages)

    messages.append({"role": "user", "content": question})
    with st.spinner("Searching the PlacidWay pages..."):
        reply = answer_question(kb, question, history, disclaimer_shown)

    if reply["answer_type"] == "error":
        # Do not keep failed exchanges in the history used for follow-ups.
        messages.pop()
        st.session_state.error = reply["answer"]
        return
    messages.append({"role": "assistant", "content": reply["answer"], "question": question, **{
        key: reply[key] for key in ("sources", "offer_quote", "show_disclaimer", "quote_url")}})


def admin_panel(kb: KnowledgeBase) -> None:
    """Refresh and log views, behind the admin token."""
    with st.sidebar.expander("Admin"):
        if not config.ADMIN_TOKEN:
            st.caption("Disabled: ADMIN_TOKEN is not set.")
            return
        token = st.text_input("Admin token", type="password")
        # compare_digest avoids leaking the token through timing differences.
        if not token or not hmac.compare_digest(token, config.ADMIN_TOKEN):
            return
        if st.button("Refresh content now"):
            try:
                summary = run_ingest()
                load_knowledge_base.clear()  # next run loads the new index
                st.success(f"Done: {summary}")
            except Exception as error:  # noqa: BLE001 - show the reason to the admin
                st.error(f"Refresh failed, old index kept: {error}")
        if st.checkbox("Show unanswered questions"):
            st.dataframe(storage.list_rows("unanswered"))
        if st.checkbox("Show leads"):
            st.dataframe(storage.list_rows("leads"))


def sidebar(kb: KnowledgeBase) -> None:
    st.sidebar.header("About")
    st.sidebar.write("Answers only from these PlacidWay pages, and always shows its source.")
    for page in kb.manifest.get("pages", {}).values():
        st.sidebar.markdown(f"- [{page['title']}]({page['url']})")
    st.sidebar.caption(f"{len(kb.chunks)} passages | last checked {kb.manifest.get('last_checked', 'unknown')}")
    if st.sidebar.button("New chat"):
        st.session_state.messages = []
        st.rerun()
    admin_panel(kb)


def main() -> None:
    kb = load_knowledge_base()
    st.session_state.setdefault("messages", [])
    sidebar(kb)

    st.title("PlacidWay Knowledge Chatbot")
    st.caption("Assessment demo. Information comes from PlacidWay pages and is not medical advice.")
    if not config.GROQ_API_KEY:
        st.warning("GROQ_API_KEY is not set, so questions cannot be answered yet.")

    # A question can come from the input box or from an example button.
    question = st.chat_input("Ask about treatments, packages or prices...",
                             max_chars=config.MAX_MESSAGE_CHARS)
    if not st.session_state.messages:
        st.write("Hi! Ask me about the ITC Immunity Therapy Center in Tijuana, its alternative "
                 "cancer treatment packages, or alternative medicine prices. For example:")
        for example in EXAMPLES:
            if st.button(example):
                question = example

    if question and question.strip():
        handle_question(kb, question.strip())
        st.rerun()  # redraw from the top so the greeting and examples disappear

    # Draw the whole conversation (Streamlit re-runs this script on every action).
    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            show_text(message["content"])
            if message["role"] == "assistant":
                show_bot_extras(message, index)

    if st.session_state.get("error"):
        st.error(st.session_state.pop("error"))


main()
