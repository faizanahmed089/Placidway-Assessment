"""Central configuration.

Every tunable value lives here so there is one place to look (and one place to
change during a review). Secrets are never hard-coded: they are read from
environment variables, which locally come from a `.env` file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file if it exists (no-op in production,
# where the hosting platform injects real environment variables).
load_dotenv()

# --------------------------------------------------------------------------
# Knowledge sources
# --------------------------------------------------------------------------
# The assessment says: "Use only these pages. Do not crawl beyond them."
# So the crawler has NO link-following logic at all; it only fetches this list.
SOURCES = [
    {
        "id": "clinic-profile",
        "page_type": "Clinic profile",
        "url": "https://www.placidway.com/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
    },
    {
        "id": "package-adenocarcinoma",
        "page_type": "Treatment package",
        "url": "https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
    },
    {
        "id": "package-adrenal",
        "page_type": "Treatment package",
        "url": "https://www.placidway.com/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
    },
    {
        "id": "package-anal",
        "page_type": "Treatment package",
        "url": "https://www.placidway.com/package/7901/Alternative-Anal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
    },
    {
        "id": "clinic-videos",
        "page_type": "Clinic videos",
        "url": "https://www.placidway.com/profile-videos/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
    },
    {
        "id": "price-list",
        "page_type": "Price list",
        "url": "https://www.placidway.com/price-list/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
    },
    {
        "id": "price-comparison",
        "page_type": "Price comparison",
        "url": "https://www.placidway.com/search-medical-pricings/Alternative-Medicine/All/1",
    },
]

# Where we send people when the bot cannot answer. Every source page carries
# PlacidWay's own "Request your Free Quote" form at the #cta-form anchor, so we
# link to that instead of guessing a URL that we never crawled.
QUOTE_URL = SOURCES[0]["url"] + "#cta-form"

# --------------------------------------------------------------------------
# Crawler politeness (required by the assessment brief)
# --------------------------------------------------------------------------
USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "PlacidWayAssessmentBot/1.0 (AI Automation Engineer assessment; fetches 7 listed pages only)",
)
ROBOTS_URL = "https://www.placidway.com/robots.txt"
CRAWL_DELAY_SECONDS = 1.2   # "about one request per second" - we stay just under
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3             # a DNS hiccup was seen during testing, so we retry

# --------------------------------------------------------------------------
# Files on disk
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
INDEX_DIR = DATA_DIR / "index"
CHUNKS_FILE = INDEX_DIR / "chunks.json"        # chunk text + metadata
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"  # one vector per chunk
MANIFEST_FILE = INDEX_DIR / "manifest.json"    # per-page content hash + timestamps
DB_FILE = DATA_DIR / "chatbot.sqlite3"         # leads + unanswered-question log
STATIC_DIR = BASE_DIR / "static"

# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------
MAX_CHUNK_CHARS = 1200  # ~300 tokens: big enough for a full "what's included" list

# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------
# Small English embedding model that runs on CPU through ONNX (no GPU, no API
# key, no cost). Questions are rewritten to English first, so English is enough.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
TOP_K = 6             # passages handed to the LLM (fewer = fewer tokens per question)
CANDIDATES_PER_RANKER = 20  # how many results each ranker contributes before merging
RRF_K = 60            # standard constant for Reciprocal Rank Fusion
RESERVED_PER_RANKING = 2  # each ranking's top hits are always kept (see knowledge_base.search)
# Relevance gate: if the best cosine similarity is below this, we treat the
# question as "not covered by the content" and give the LLM no passages.
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.55"))

# --------------------------------------------------------------------------
# LLM (Groq free tier)
# --------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Larger model writes the grounded answer; small fast model rewrites the query.
ANSWER_MODEL = os.getenv("GROQ_ANSWER_MODEL", "openai/gpt-oss-120b")
REWRITE_MODEL = os.getenv("GROQ_REWRITE_MODEL", "openai/gpt-oss-20b")
# Groq's free tier limits EACH model separately (about 200,000 tokens per day
# and 8,000 per minute). When the first model's quota is used up, the next one
# in the list is tried, so the public demo keeps answering instead of going
# down. The guardrail checks in code apply whichever model answers.
FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "GROQ_FALLBACK_MODELS", "qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",") if m.strip()]
# These are "reasoning" models: they think before writing, and that thinking is
# billed against the output-token limit. "low" keeps it short, which is enough
# here because the task is "read the passages and report", not problem solving.
# Set to an empty string for models that do not accept this setting.
REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "low")

# --------------------------------------------------------------------------
# Chat limits (protect the free-tier quota on a public demo)
# --------------------------------------------------------------------------
MAX_MESSAGE_CHARS = 600
MAX_HISTORY_TURNS = 6   # only the most recent turns are used for follow-ups

# --------------------------------------------------------------------------
# Admin / refresh
# --------------------------------------------------------------------------
# Token required by the /api/admin/* endpoints. If it is empty, those endpoints
# are disabled entirely (safer default than an open refresh button).
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
# Re-crawl automatically every N hours while the server is running. 0 = off.
AUTO_REFRESH_HOURS = float(os.getenv("AUTO_REFRESH_HOURS", "24"))
