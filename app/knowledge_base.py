"""The searchable knowledge base: load chunks from disk and retrieve the most
relevant ones for a question.

Retrieval is HYBRID - two rankers that fail in different ways:
  * BM25 (keyword search)  : great at exact words such as "LAK", "ozone",
                             "in-patient"; blind to paraphrases.
  * Embeddings (meaning)   : understands "how much" ~ "cost" ~ "price";
                             weaker on rare exact terms.
Their two rankings are merged with Reciprocal Rank Fusion (RRF).

There is no vector database on purpose: 7 pages produce roughly a hundred
chunks, so a NumPy matrix searched by brute force answers in a few
milliseconds and leaves nothing to install, host or pay for.
"""

import json
import logging
import re
import threading

import numpy as np
from rank_bm25 import BM25Okapi

from app import config
from app.chunker import chunk_search_text

log = logging.getLogger(__name__)

# The embedding model takes a moment to load, so it is created once and
# shared. The lock stops two threads from loading it at the same time.
_embedder = None
_embedder_lock = threading.Lock()


def get_embedder():
    """Return the shared fastembed model, loading it on first use."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            from fastembed import TextEmbedding  # imported lazily: slow import
            log.info("Loading embedding model %s", config.EMBEDDING_MODEL)
            _embedder = TextEmbedding(model_name=config.EMBEDDING_MODEL)
        return _embedder


def _normalise(vectors: np.ndarray) -> np.ndarray:
    """Scale every vector to length 1, so a dot product equals cosine similarity."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def embed_passages(texts: list[str]) -> np.ndarray:
    """Embed chunk texts (used at ingestion time)."""
    vectors = np.array(list(get_embedder().embed(texts)), dtype=np.float32)
    return _normalise(vectors)


def embed_query(text: str) -> np.ndarray:
    """Embed a question. `query_embed` adds the prefix this model family
    expects for search queries."""
    vector = np.array(next(iter(get_embedder().query_embed(text))), dtype=np.float32)
    return _normalise(vector)


def _stem(word: str) -> str:
    """Very light stemming so word forms match in keyword search:
    'include', 'includes', 'included', 'including' -> 'includ'.
    Without it, "what does it include?" does not keyword-match a section
    titled "Included in the In-Patient Program" (found during testing)."""
    if word.isdigit() or len(word) <= 3:
        return word
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 3 else word


def tokenize(text: str) -> list[str]:
    """Lower-case, stemmed word tokens for BM25. '$18,995' -> '18995' so a
    price typed with or without a comma matches the same token."""
    return [_stem(word) for word in re.findall(r"[a-z0-9]+", text.lower().replace(",", ""))]


class KnowledgeBase:
    """An immutable, in-memory snapshot of the index.

    A refresh builds a brand-new KnowledgeBase and swaps it in, so a chat
    request that is in progress never sees a half-updated index.
    """

    def __init__(self, chunks: list[dict], embeddings: np.ndarray, manifest: dict):
        if len(chunks) != len(embeddings):
            raise ValueError("chunks.json and embeddings.npy are out of sync - rebuild the index")
        self.chunks = chunks
        self.embeddings = embeddings
        self.manifest = manifest
        self.bm25 = BM25Okapi([tokenize(chunk_search_text(c)) for c in chunks])

    @classmethod
    def load(cls) -> "KnowledgeBase":
        """Read the index files written by ingest.py."""
        chunks = json.loads(config.CHUNKS_FILE.read_text(encoding="utf-8"))
        # The vectors file is binary, so it is not committed to git (Hugging
        # Face rejects plain binary files). When it is missing - a fresh clone
        # or a new Docker image - it is recomputed from chunks.json, which
        # takes a few seconds and needs no crawling.
        if config.EMBEDDINGS_FILE.exists():
            embeddings = np.load(config.EMBEDDINGS_FILE)
        else:
            log.info("Embeddings file missing - computing vectors for %s chunks", len(chunks))
            embeddings = embed_passages([chunk_search_text(c) for c in chunks])
            np.save(config.EMBEDDINGS_FILE, embeddings)
        manifest = json.loads(config.MANIFEST_FILE.read_text(encoding="utf-8"))
        return cls(chunks, embeddings, manifest)

    def search(self, query: str, alternative: str = "",
               top_k: int = config.TOP_K) -> tuple[list[dict], float]:
        """Return (best chunks, best cosine similarity).

        `alternative` is an optional second wording of the same question (see
        the rewrite prompt). Searching with both wordings catches vocabulary
        gaps such as "not included" vs the page's heading "Excluded Services".

        The similarity is returned separately because the caller uses it as a
        relevance gate: a low value means "nothing on the site is about this".
        """
        queries = [query] + ([alternative] if alternative and alternative != query else [])
        similarities = np.zeros(len(self.chunks), dtype=np.float32)
        rankings = []
        for text in queries:
            # --- Ranker 1: semantic similarity (dot product of unit vectors).
            scores = self.embeddings @ embed_query(text)
            rankings.append(np.argsort(-scores)[: config.CANDIDATES_PER_RANKER])
            similarities = np.maximum(similarities, scores)  # best score over both wordings

            # --- Ranker 2: BM25 keyword score. Chunks scoring 0 share no word
            # with the query, so they are left out of the keyword ranking.
            keyword_scores = self.bm25.get_scores(tokenize(text))
            rankings.append([i for i in np.argsort(-keyword_scores)[: config.CANDIDATES_PER_RANKER]
                             if keyword_scores[i] > 0])

        # --- Merge with Reciprocal Rank Fusion. Each ranking gives a chunk
        # 1 / (RRF_K + rank). Using ranks instead of raw scores avoids having
        # to put BM25 scores and cosine similarities on the same scale.
        fused: dict[int, float] = {}
        for order in rankings:
            for rank, index in enumerate(order):
                fused[int(index)] = fused.get(int(index), 0.0) + 1.0 / (config.RRF_K + rank + 1)

        # --- Pick the top results, keeping ONE copy of duplicated passages.
        # Some text is printed word-for-word on several pages (the "About ITC"
        # blurb; the in-patient inclusions on all three package pages). One
        # copy is enough evidence, but it must be the copy from the page the
        # visitor asked about, or the answer would cite the wrong page. The
        # embedding includes the page title, so among identical texts the copy
        # with the highest similarity is the one whose page matches the question.
        best_copy: dict[str, int] = {}
        for index, chunk in enumerate(self.chunks):
            text = chunk["text"]
            if index in fused and (text not in best_copy
                                   or similarities[index] > similarities[best_copy[text]]):
                best_copy[text] = index

        # --- Order of selection. RRF favours chunks that several rankings
        # agree on, which can push out a chunk that ONE ranking is very sure
        # about (testing found the "Excluded Services" section ranked #1 by
        # keywords but dropped). So the top hits of every ranking are taken
        # first, and the remaining places are filled in fused order.
        by_fused = sorted(fused, key=fused.get, reverse=True)
        reserved = {int(index) for order in rankings for index in order[: config.RESERVED_PER_RANKING]}
        selection_order = [i for i in by_fused if i in reserved] + [i for i in by_fused if i not in reserved]

        results, seen_texts = [], set()
        for index in selection_order:
            text = self.chunks[index]["text"]
            if text in seen_texts:
                continue
            seen_texts.add(text)
            chosen = best_copy[text]
            results.append({**self.chunks[chosen], "similarity": float(similarities[chosen])})
            if len(results) == top_k:
                break

        best_similarity = float(similarities.max()) if len(similarities) else 0.0
        return results, best_similarity
