# Architecture (draft v0, 2026-11-22)

Principle carried over from the first project: **the model never computes or types a number.**
It plans; deterministic code computes; an independent verifier checks every figure; otherwise the
answer is withheld.

## Layers

1. Ingestion (automated, nightly): AMFI/mfapi deltas, RBI series, with data contracts.
   A failed contract blocks publishing and opens an issue; it never silently loads.
2. Data quality (rules and thresholds today; ML only if it beats them on the same test): detect unit splits/NAV resets, bad values, stale runs, gaps.
   Evaluated by injecting known anomalies and by checking real cases (e.g. scheme 119164, 2022-11-27).
   Output: an adjustment table with a reason code. Raw data is never overwritten.
3. Storage: Parquet and DuckDB for heavy local analytics and CI; Postgres (+pgvector) holds the
   published subset for serving (Neon free, 1 GB: active Direct+Growth funds, metals, FX).
4. Metric engine: returns (point to point, CAGR, rolling), SIP XIRR, volatility, max drawdown,
   Sharpe/Sortino, beta, tracking error, up/down capture, correlation. Two independent
   implementations (SQL and numpy); the verifier recomputes from raw rows and a disagreement
   withholds the answer.
5. Entity resolution: "sbi small cap" to one scheme code (lexical trigram plus embeddings, ISIN
   match). Ambiguous names get a clarifying question; the resolved scheme code is always shown.
6. Planner (LLM): turns a question into a DAG of calls to the metric engine. It can chain steps
   but cannot compute, browse, or act. Every node's output is verified.
7. Documents (later): AMC factsheets and SEBI circulars, hybrid keyword plus vector search,
   quotes verified against stored text, as in the first project.
8. Explanations: code writes every result sentence; definitions come from a fixed, versioned glossary
   (data/glossary.json). Model-written explanations were tested and rejected (docs/MODEL_RUN_2.md).
   The user's own key is used for planning only.
9. Evals: pre-registered dev and locked sets, one shot per model, no re-scoring after reading.

## News lane (phase 4, after the funds core)

A separate lane from verified numbers. Nothing here is mixed into a computed result.

- Collector: scheduled, no AI, no key. Pulls from an allowlist of sources (RBI, SEBI, AMFI, exchange
  announcements, publisher RSS where terms allow). Stores source, URL, timestamp, raw text.
- Summariser: on demand, on the user's own key. Summaries cite stored items; quotes are checked by
  code against stored text (VERIFIED_QUOTE). Fetched text is untrusted data; the model has no
  tools that act.
- Numbers inside news get the label ATTRIBUTED ("reported by <source>, not verified by us"),
  never VERIFIED.
- Watchlist config: entities, sources, check interval, daily token budget. Free-tier keys cannot
  sustain an always-on agent, so collection is keyless and only summarising spends the key.
- Says what happened, not what it means for price (prediction and SEBI risk).
- Transport: polling or server-sent events. Serverless hosting cannot hold websockets, and no free
  live tick feed has been verified (UNVERIFIED). Source reliability and terms are tested before build.

## Scenario analysis, not prediction

No NAV or price forecasts as a product. Instead: historical rolling-return distributions and
block-bootstrap SIP outcomes, labelled as illustrations from past data. Any forecasting model is
admitted only if it beats a naive baseline in walk-forward tests; a negative result is published.

## Scope and kill criteria

- Public: funds (active Direct+Growth), RBI gold/silver monthly, FX. Local only: NSE 500 stocks.
- Stocks ship only if adjusted prices are verified on known splits/bonuses.
- If entity resolution or the data-quality layer cannot meet a pre-registered bar, we narrow scope,
  not the bar.

## Will not do

Autonomous agents that act or trade; open web browsing inside the answer path (prompt-injection risk;
the news lane below is the only exception and is bounded);
buy/sell/pick directives; unadjusted returns; claiming accuracy without a pre-registered eval.
