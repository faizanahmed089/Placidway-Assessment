# PlacidWay Website Knowledge Chatbot

A chatbot that answers visitor questions using **only** the 7 PlacidWay pages
listed in the assessment brief. It cites the page each answer came from, says
"I don't know" when the pages do not contain the answer, and refuses to
confirm prices that are not on the pages.

## How it works

```
INGESTION  (python -m app.ingest, the refresh endpoint, or the daily auto-refresh)

  7 URLs ──> crawler.py ──> extractor.py ──> chunker.py ──> knowledge_base.py ──> data/index/
             robots.txt     strip nav,       split by       embed each chunk      chunks.json
             User-Agent     pop-ups,         heading,       (local CPU model)     embeddings.npy
             1 req/sec      comments;        keep page                            manifest.json
             retries        label table      title + URL
                            rows

ANSWERING  (POST /api/chat  ->  app/chat.py)

  message + history
     │
     ├─ 1. REWRITE   small LLM: follow-up / Spanish / Arabic -> standalone English query,
     │               plus a second wording with synonyms ("not included" -> "excluded")
     ├─ 2. RETRIEVE  BM25 keywords + embeddings for both wordings, merged with Reciprocal
     │               Rank Fusion; each ranking's top 2 hits are always kept; top 6 passages
     ├─ 3. GATE      best similarity < 0.55 ?  -> LLM receives NO passages
     ├─ 4. GENERATE  visitor figures not on the pages are masked; LLM answers from the
     │               passages only and returns JSON
     │               {answer_type, answer, sources:[passage numbers], offer_quote, ...}
     ├─ 5. VERIFY    Python: every number in the answer must exist in the passages,
     │               no URLs, a factual answer must cite a passage.
     │               Fail -> one retry with the reason -> fail again -> fixed fallback
     └─ 6. RESPOND   passage numbers -> page links; quote offer; disclaimer; log gaps
```

## How it avoids inventing answers

| Layer | Where | What it does |
|---|---|---|
| Closed source list | `config.SOURCES`, `crawler.py` | Only the 7 URLs are fetched. There is no link-following code. |
| Clean extraction | `extractor.py` | Only the page's title/price header and main body are read. "Related clinics" carousels, navigation, pop-ups and hidden HTML comments are dropped, so the bot cannot quote content from other pages. |
| Labelled prices | `extractor.py` | Table rows become `Program Type: Out-Patient \| Total Cost (USD): $18,995`, so a price never loses its label. A price row with no procedure name is dropped. |
| Relevance gate | `chat.py` | Off-topic questions reach the LLM with no passages, so there is nothing to answer from. |
| Strict prompt | `prompts.py` | Passages only; copy prices exactly with currency and context; never repeat a visitor's number; compare only if both sides are present; no medical advice; no bookings. |
| Wrong-price masking | `guardrails.py` | A figure the visitor typed that is not in the passages ("I heard it costs $50") is replaced with a placeholder before the LLM sees it, so the model cannot agree with it or repeat it. |
| Number check | `guardrails.py` | Deterministic: any number in the answer that is not in the retrieved passages rejects the answer. An answer that quotes a figure must also cite a page. |
| Code-built citations | `chat.py` | The LLM returns passage numbers; code maps them to URLs. A cited link can only be one of the 7 pages. |
| Fixed fallback | `chat.py` | If verification fails twice, the generated text is discarded and a fixed "I couldn't find a reliable answer, request a free quote" message is shown. |

Known gap: the number check proves a number is *on the page*, not that it is
attached to the right thing. Mixing up two real prices is prevented only by
the prompt and by keeping labels next to numbers.

## Tools and models, and why

| Part | Choice | Why |
|---|---|---|
| Language | Python | Readable, strong HTML and retrieval libraries. |
| Crawling | `requests`, `urllib.robotparser` | The pages are server-rendered HTML; no headless browser is needed. |
| Parsing | `BeautifulSoup` | Fine-grained control over what is kept and dropped. |
| Keyword search | `rank-bm25` with light stemming | Exact terms such as "LAK" or "ozone" must match; stemming lets "include" match "Included". |
| Embeddings | `fastembed` with `BAAI/bge-small-en-v1.5` | Runs on CPU, free, no API key. English-only is enough because queries are rewritten to English first. |
| Vector store | NumPy array on disk | About 100 chunks; brute-force search takes milliseconds. A vector database would add setup and nothing else. |
| LLM | Groq free tier: `openai/gpt-oss-120b` (answers), `openai/gpt-oss-20b` (query rewrite) | Free, fast, supports JSON output. These were the general-purpose chat models available on the free tier at build time; reasoning effort is set to low. If a model's free quota is used up, the next model in `GROQ_FALLBACK_MODELS` answers instead. All calls go through `app/llm.py`, so the provider can be swapped in one file. |
| Public demo UI | Streamlit (`streamlit_app.py`) | Streamlit Community Cloud hosts it free, straight from GitHub. It calls the same `answer_question()` pipeline. |
| API + alternative UI | FastAPI + one static HTML file | JSON API and admin endpoints for local or Docker use. |
| Storage | SQLite | Leads and the unanswered-question log, with no server to run. |
| Hosting | Streamlit Community Cloud | Free public URL with no payment card; visitors need no login. A `Dockerfile` is included for any Docker host. |

## Project layout

```
app/
  config.py          all settings: source URLs, thresholds, model names
  crawler.py         polite fetching (robots.txt, User-Agent, rate limit, retries)
  extractor.py       HTML -> clean text blocks
  chunker.py         text blocks -> passages with metadata
  knowledge_base.py  embeddings + BM25 + hybrid search
  ingest.py          crawl -> extract -> chunk -> embed -> save (CLI + refresh)
  llm.py             Groq wrapper (JSON in, dict out)
  prompts.py         the two prompts
  guardrails.py      number check and link check
  chat.py            the 6-step answering pipeline
  storage.py         SQLite: leads + unanswered questions
  main.py            FastAPI routes (JSON API + admin endpoints)
streamlit_app.py     Streamlit chat UI used for the public demo
static/index.html    plain HTML chat UI served by the FastAPI app
scripts/run_test_questions.py   runs the assessment's test questions
tests/               unit tests (no network, no API key)
data/index/          the built knowledge base (chunks committed; vectors rebuilt on first start)
```

## Setup

Requires Python 3.11 or newer (developed on 3.14).

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

(on macOS/Linux: `source .venv/bin/activate`)

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `GROQ_API_KEY` (free at
https://console.groq.com/keys). Optionally set `ADMIN_TOKEN` to enable the
admin endpoints.

Run the demo UI:

```bash
streamlit run streamlit_app.py
```

Or run the FastAPI version (JSON API, admin endpoints, plain HTML chat page at
http://localhost:8000):

```bash
uvicorn app.main:app --reload
```

The first start downloads the embedding model (about 65 MB) once.

## Refreshing the content

Three ways, all running the same `run_ingest()` function:

1. **Command line:** `python -m app.ingest` (add `--force` to rebuild even if nothing changed).
2. **In the demo:** sidebar -> Admin -> enter the admin token -> "Refresh content now".
   (FastAPI version: `POST /api/admin/refresh` with header `X-Admin-Token`.)
3. **Automatic:** the pages are re-checked every 24 hours (`AUTO_REFRESH_HOURS`, 0 turns it off).

A refresh re-fetches the 7 pages, hashes the *extracted text* of each one and
rebuilds the index only if a hash changed. If any page fails to download or
parse, the refresh aborts and the previous index keeps serving.

## Admin views

In the demo, the sidebar's Admin section (token required) also shows the
unanswered-question log and the captured leads. The FastAPI version exposes
the same data as JSON:

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Pages in the index, chunk counts, when it was built and last checked |
| `GET /api/admin/unanswered` | Questions the bot could not answer (content gaps), newest first |
| `GET /api/admin/leads` | Names and emails left by visitors asking for a quote |

Admin features are disabled when `ADMIN_TOKEN` is not set.

## Nice-to-have features included

- **Answers in the visitor's language:** the query is translated to English for search; the answer is written in the original language.
- **Follow-up questions:** the rewrite step resolves "it" / "there" from chat history.
- **Medical disclaimer:** shown once per conversation, only on answers about treatments.
- **Lead capture:** a name + email form appears when the bot cannot answer or the visitor asks for a quote.
- **Unanswered-question log:** stored with the similarity score, so a low score points to a missing topic.

## Tests

```bash
pytest
```

16 unit tests cover the number check, wrong-price masking, link check,
keyword stemming, table extraction, noise removal and chunk metadata.

```bash
python -m scripts.run_test_questions
```

Runs the assessment's test questions through the live pipeline (needs
`GROQ_API_KEY`) and writes [test_results.md](test_results.md).

## Deployment

The live demo runs on Streamlit Community Cloud from this repository
(`streamlit_app.py`, secrets `GROQ_API_KEY` and `ADMIN_TOKEN`). Steps are in
[DEPLOY.md](DEPLOY.md). The `Dockerfile` runs the FastAPI version on any
Docker host.

## Free-tier limits

Groq's free tier allows, per model, about 8,000 tokens per minute and 200,000
tokens per day. One question uses roughly 3,000 tokens, so one model covers
about 60 questions a day and 2 a minute. When a model is rate limited the bot
switches to the next model in the fallback list; if all are exhausted it shows
a "try again in a moment" message rather than an answer.

## Known limitations

See [WRITEUP.md](WRITEUP.md).
