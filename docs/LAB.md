# Forecast Lab: what was tried and what survived

The verified platform never predicts. The Lab asks a separate question: *can any model add something real beyond simple methods?* Every experiment was **pre-registered** (rules, universe, scoring and pass bar written before any model ran), run **walk-forward** (nothing sees the future), and judged against **simple baselines**. A model that does not clear its bar is published as a negative result and is not shown in the product.

Same data throughout: 256 long-lived equity-oriented funds (survivorship bias acknowledged), 2014 to 2026.

| # | Experiment | Verdict | Headline |
|---|---|---|---|
| 1 | 21-day volatility forecast ([doc](LAB_1_VOLATILITY.md)) | **Passed, modestly** | GARCH(1,1)-t had the lowest loss, better than the HAR baseline in 6 of 8 years. Post-hoc checks: not clearly better than a plain EWMA, and the edge shrinks once funds are not treated as independent. LightGBM failed. |
| 2 | 80% return ranges, 1 year ([doc](LAB_2_RETURN_RANGES.md)) | **Failed** | Best coverage 77.4% overall (pooled percentiles), but swinging between about 15% and 98% by year for every method. Not shown. |
| 3 | Market regime labels, 3-state HMM ([doc](LAB_3_REGIMES.md)) | **Failed on stability** | Separated future volatility well (10.9% / 14.1% / 19.9%, ordered in 7 of 8 years) but flipped label about 38 times a year against 16 for a trivial rival. Not shown. |
| 4 | Peer finding with a trained transformer ([doc](LAB_4_PEER_EMBEDDINGS.md)) | **Failed** | 54.0% same-category in the top 5 versus 59.2% for PCA and 58.3% for plain correlation. A random-weights copy scored 53.6%: training added nothing measurable. |

## What this adds up to
- One usable estimate (volatility), with its limits stated.
- Three clean negatives. The common cause is a short window with one crash, heavy regime change between years, and strong simple baselines.
- A side finding: plain return correlation finds a same-category peer about 58% of the time with no ML.
- The discipline is the product: pre-registration, baselines, controls, post-hoc checks labelled as post-hoc, and the willingness to withhold.

## Reproduce
`python lab/vol_forecast.py`, `python lab/vol_posthoc.py`, `python lab/range_forecast.py`, `python lab/regime_detection.py`, `python lab/embedding_peers.py` (needs `arch`, `lightgbm`, `hmmlearn`, `torch`; see `requirements-lab.txt`). Results land in `lab/results/`.

## Limits
One data window and one fund set per experiment; fixed untuned settings; nothing here is investment advice or a prediction of any fund's return.
