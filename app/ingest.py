"""Ingestion pipeline: crawl -> extract -> chunk -> embed -> save.

Run it from the project root to build or refresh the knowledge base:

    python -m app.ingest            # rebuild only if a page changed
    python -m app.ingest --force    # rebuild regardless

The same `run_ingest()` function is called by the server's refresh endpoint
and by the daily auto-refresh, so there is exactly one code path for updates.
"""

import argparse
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import numpy as np

from app import config
from app.chunker import chunk_page, chunk_search_text
from app.crawler import fetch_sources
from app.extractor import extract_page
from app.knowledge_base import embed_passages

log = logging.getLogger(__name__)


def _content_hash(chunks: list[dict]) -> str:
    """Fingerprint of a page's extracted text. We hash the cleaned text, not
    the raw HTML, because the raw HTML changes on every request (tokens,
    view counters) even when the visible content is identical."""
    joined = "\n".join(chunk["text"] for chunk in chunks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _load_manifest() -> dict:
    if config.MANIFEST_FILE.exists():
        return json.loads(config.MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def _write_atomically(path, write_function) -> None:
    """Write to a temporary file, then rename it over the real one. A crash
    halfway through therefore never leaves a corrupt index on disk."""
    temporary = path.with_name(path.name + ".tmp")
    write_function(temporary)
    os.replace(temporary, path)


def run_ingest(force: bool = False) -> dict:
    """Build or refresh the index. Returns a short summary dict.

    If any page cannot be fetched or parsed, an exception is raised BEFORE
    anything is written - the previous good index stays in place.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old_manifest = _load_manifest()
    old_pages = old_manifest.get("pages", {})

    # 1. Crawl (robots.txt, User-Agent and rate limit are handled inside).
    pages = fetch_sources()

    # 2 + 3. Extract clean text and cut it into chunks.
    all_chunks: list[dict] = []
    page_records: dict[str, dict] = {}
    changed: list[str] = []
    for page in pages:
        extracted = extract_page(page["html"])
        chunks = chunk_page(page, extracted)
        if not chunks:
            raise ValueError(f"No content extracted from {page['url']}")
        digest = _content_hash(chunks)
        if old_pages.get(page["id"], {}).get("hash") != digest:
            changed.append(page["id"])
        page_records[page["id"]] = {
            "url": page["url"],
            "title": extracted["title"],
            "hash": digest,
            "chunks": len(chunks),
        }
        all_chunks.extend(chunks)

    # Nothing changed -> keep the existing index, just record that we checked.
    index_exists = config.CHUNKS_FILE.exists() and config.EMBEDDINGS_FILE.exists()
    same_model = old_manifest.get("embedding_model") == config.EMBEDDING_MODEL
    if not force and not changed and index_exists and same_model:
        old_manifest["last_checked"] = now
        _write_atomically(config.MANIFEST_FILE,
                          lambda p: p.write_text(json.dumps(old_manifest, indent=2), encoding="utf-8"))
        log.info("No page changed - index left as is")
        return {"rebuilt": False, "changed_pages": [], "chunks": len(all_chunks)}

    # 4. Embed every chunk. (With ~100 chunks this takes seconds on a CPU, so
    # a full re-embed is simpler and safer than patching individual pages.)
    log.info("Embedding %s chunks", len(all_chunks))
    embeddings = embed_passages([chunk_search_text(c) for c in all_chunks])

    # 5. Save chunks, vectors and a manifest describing this build.
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "built_at": now,
        "last_checked": now,
        "embedding_model": config.EMBEDDING_MODEL,
        "pages": page_records,
    }
    _write_atomically(config.CHUNKS_FILE,
                      lambda p: p.write_text(json.dumps(all_chunks, indent=2, ensure_ascii=False), encoding="utf-8"))
    # np.save appends ".npy" unless given an open file, hence the file handle.
    def _save_vectors(path):
        with open(path, "wb") as handle:
            np.save(handle, embeddings)
    _write_atomically(config.EMBEDDINGS_FILE, _save_vectors)
    _write_atomically(config.MANIFEST_FILE,
                      lambda p: p.write_text(json.dumps(manifest, indent=2), encoding="utf-8"))

    log.info("Index rebuilt: %s chunks from %s pages (changed: %s)",
             len(all_chunks), len(pages), changed or "forced")
    return {"rebuilt": True, "changed_pages": changed, "chunks": len(all_chunks)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build or refresh the chatbot knowledge base")
    parser.add_argument("--force", action="store_true", help="rebuild even if no page changed")
    arguments = parser.parse_args()
    print(run_ingest(force=arguments.force))
