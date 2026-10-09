# Write-up: limitations and what I would do with another week

## Known limitations

- **The number check verifies presence, not meaning.** It guarantees every
  figure in an answer exists in the retrieved passages. It cannot tell that a
  real price was attached to the wrong program. That case relies on the prompt
  and on extraction keeping each price beside its label.
- **Three package pages are near-duplicates.** Adenocarcinoma, adrenal and
  anal cancer packages share the same prices and structure. If a visitor does
  not name the cancer type, retrieval may return any of the three; the answer
  is still correct for the page it cites.
- **The extractor is tied to PlacidWay's current HTML** (`div.pack-title-price-header`
  and `main.article-dt-desc`). If the layout changes, ingestion raises an error
  and keeps the old index rather than indexing an empty page, but a person has
  to update the selectors.
- **Only server-rendered content is read.** The price comparison page has a
  "Load More" button; clinics loaded by JavaScript after the first five are not
  in the knowledge base.
- **The fixed fallback message is English only.** Normal answers follow the
  visitor's language; the safety fallback used after two failed verifications
  does not.
- **Free-tier limits.** Groq allows about 200,000 tokens per day and 8,000 per
  minute per model, roughly 60 questions a day and 2 a minute on one model.
  The bot falls back to two other models when one is exhausted, but there is
  no per-visitor rate limiting, so heavy use of the public demo can still use
  up the quota. The bot then shows a "try again in a moment" message. Answers
  from the smaller fallback models pass the same code checks but may be worded
  less well.
- **Hosting is ephemeral.** On the free Streamlit Community Cloud tier the app
  sleeps after a period without visitors (the next visitor has to wake it and
  wait), and its disk resets on restart, so leads and the unanswered-question
  log are lost, and the index returns to the committed version until the next
  refresh. The Docker image has not been built or run.
- **The LLM is not perfectly repeatable.** Even at temperature 0 the same
  question can be worded or classified slightly differently between runs
  (for example a correct refusal labelled `not_found` one time and `answered`
  the next). The code checks do not depend on that label.
- **The relevance threshold (0.55) was tuned by hand** on about 20 sample
  questions, not on a labelled evaluation set.

## With another week

1. **Evaluation set.** 50-100 questions with expected facts and expected
   behaviour (answer / decline / refuse), run automatically on every change,
   reporting grounding and refusal accuracy. This would replace hand-tuning of
   the threshold and prompt.
2. **Claim-level verification.** A second LLM pass that checks each sentence
   of the answer against the cited passage ("is this supported: yes/no"),
   closing the "right number, wrong label" gap.
3. **Structured price table.** Parse every price into rows
   (treatment, program, clinic, location, amount, currency, qualifier, URL) and
   answer cost questions from that table directly instead of from free text.
4. **Persistent storage and alerts.** Move leads and logs to a hosted database,
   send leads to PlacidWay's CRM, and alert when a refresh fails or a page's
   content changes sharply.
5. **Rate limiting and caching.** Per-visitor limits, and a cache for repeated
   questions to save quota and latency.
6. **Reranking and multilingual embeddings.** A cross-encoder reranker over
   the top 20 candidates, and a multilingual embedding model so retrieval does
   not depend on the query translation step.
7. **Streaming answers** in the UI, with verification applied before the text
   is revealed.
