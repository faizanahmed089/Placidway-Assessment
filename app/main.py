"""FastAPI web server: serves the chat page and the JSON API.

Run locally with:
    uvicorn app.main:app --reload

Endpoints
    GET  /                       chat UI (static/index.html)
    POST /api/chat               ask a question
    POST /api/lead               save name + email for a quote request
    GET  /api/health             index status (which pages, when last refreshed)
    POST /api/admin/refresh      re-crawl the pages now          (needs admin token)
    GET  /api/admin/unanswered   questions the bot could not answer (needs admin token)
    GET  /api/admin/leads        captured leads                  (needs admin token)
"""

import hmac
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import config, storage
from app.chat import answer_question
from app.ingest import run_ingest
from app.knowledge_base import KnowledgeBase, get_embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # hide per-request HTTP noise
log = logging.getLogger(__name__)

# The knowledge base currently being served. A refresh replaces this reference
# with a freshly loaded one; requests already running keep using the old one.
_kb: KnowledgeBase | None = None
# Only one refresh at a time (manual and automatic refreshes could overlap).
_refresh_lock = threading.Lock()


def refresh_knowledge_base(force: bool = False) -> dict:
    """Re-crawl the source pages and swap in the new index if it changed."""
    global _kb
    with _refresh_lock:
        summary = run_ingest(force=force)
        if summary["rebuilt"] or _kb is None:
            _kb = KnowledgeBase.load()
        return summary


def _auto_refresh_loop() -> None:
    """Background thread: refresh every AUTO_REFRESH_HOURS. A failed refresh
    is logged and the previous index keeps serving."""
    while True:
        time.sleep(config.AUTO_REFRESH_HOURS * 3600)
        try:
            log.info("Auto-refresh: %s", refresh_knowledge_base())
        except Exception:  # noqa: BLE001 - the loop must survive any failure
            log.exception("Auto-refresh failed; keeping the existing index")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Runs once when the server starts."""
    global _kb
    storage.init_db()

    if config.CHUNKS_FILE.exists() and config.MANIFEST_FILE.exists():
        _kb = KnowledgeBase.load()            # normal case: index shipped with the app
    else:
        refresh_knowledge_base(force=True)    # first run: build it now
    get_embedder()                            # load the model now, not on the first question
    log.info("Knowledge base ready: %s chunks", len(_kb.chunks))

    if config.AUTO_REFRESH_HOURS > 0:
        threading.Thread(target=_auto_refresh_loop, daemon=True).start()
    if not config.GROQ_API_KEY:
        log.warning("GROQ_API_KEY is not set - chat requests will fail until it is")
    yield


app = FastAPI(title="PlacidWay Knowledge Chatbot", lifespan=lifespan)


# --------------------------------------------------------------------------
# Request bodies. Pydantic validates types and lengths before our code runs,
# so oversized or malformed input is rejected with a 422 automatically.
# --------------------------------------------------------------------------
class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=config.MAX_MESSAGE_CHARS)
    # History is kept in the browser and sent with each request, so the server
    # stores no conversations and needs no sessions.
    history: list[Turn] = Field(default_factory=list, max_length=40)
    disclaimer_shown: bool = False


class LeadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    question: str = Field(default="", max_length=config.MAX_MESSAGE_CHARS)


def _require_admin(token: str | None) -> None:
    """Admin endpoints are off unless ADMIN_TOKEN is configured, and the
    caller must send the same value in the X-Admin-Token header."""
    if not config.ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="Admin endpoints are disabled")
    # compare_digest avoids leaking the token through response timing.
    if not token or not hmac.compare_digest(token, config.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# --------------------------------------------------------------------------
# Routes. They are plain `def` (not `async def`) on purpose: the work inside
# is blocking (LLM call, embedding), and FastAPI runs plain functions in a
# thread pool so one slow request does not freeze the others.
# --------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def chat_page() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    history = [turn.model_dump() for turn in request.history]
    return answer_question(_kb, request.message, history, request.disclaimer_shown)


@app.post("/api/lead")
def lead(request: LeadRequest) -> dict:
    storage.save_lead(request.name.strip(), request.email.strip(), request.question.strip())
    return {"ok": True}


@app.get("/api/health")
def health() -> dict:
    manifest = _kb.manifest
    return {
        "status": "ok",
        "chunks": len(_kb.chunks),
        "built_at": manifest.get("built_at"),
        "last_checked": manifest.get("last_checked"),
        "pages": [{"url": page["url"], "title": page["title"], "chunks": page["chunks"]}
                  for page in manifest.get("pages", {}).values()],
    }


@app.post("/api/admin/refresh")
def admin_refresh(force: bool = False, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        return refresh_knowledge_base(force=force)
    except Exception as error:  # crawl or parse failure: old index is untouched
        log.exception("Manual refresh failed")
        raise HTTPException(status_code=502, detail=f"Refresh failed: {error}") from error


@app.get("/api/admin/unanswered")
def admin_unanswered(x_admin_token: str | None = Header(default=None)) -> list[dict]:
    _require_admin(x_admin_token)
    return storage.list_rows("unanswered")


@app.get("/api/admin/leads")
def admin_leads(x_admin_token: str | None = Header(default=None)) -> list[dict]:
    _require_admin(x_admin_token)
    return storage.list_rows("leads")
