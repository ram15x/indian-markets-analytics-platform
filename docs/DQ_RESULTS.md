# Data-quality layer: results (2026-11-22)

Universe: 1,772 active Direct+Growth schemes, 2,978,587 NAV rows (AMFI archive v2026.11.22).
The earlier "1,799" counted Bonus and IDCW options; the loader now excludes them and keeps
"Dividend Yield" funds (a category, not a payout option).

## Pre-registered evaluation (docs/DQ_EVAL.md)
Injected anomalies into schemes with no real move over 10%. Dev = even scheme codes, locked = odd,
locked scored once. Bars were set before running; two amendments to thresholds were made on dev
evidence and are recorded in DQ_EVAL.md. One code bug (adjustment factor stored inverted) was found
because the harness checked the adjusted series, not only detection.

| Measure | Bar | Dev (n=299) | Locked (n=300) |
|---|---|---|---|
| Scale change recall | >= 0.99 | 1.00 | 1.00 (66/66) |
| Scale change precision, exact k | >= 0.99 | 1.00 | 1.00 |
| Adjusted series vs clean, max rel. error | 1e-6 | 0 | 0 |
| Bad value recall | >= 0.95 | 1.00 | 0.983 (57/58) |
| Persistent real-like moves adjusted | 0 | 0 | 0 |
| No-event schemes with any adjustment | 0 | 0 | 0 |
| Transient shift recall (no bar set) | n/a | 1.00 | 1.00 |

Locked set also had 1 event outside an injected date (not investigated or tuned, per protocol).

## Real data (no ground truth except the cases named)
- 21 scale changes in 20 schemes (19 x100, 2 x10), all liquid/overnight/money-market style face-value
  changes. Known cases handled: 119164 (x100 in 2014, /100 in 2022), 120304 (/10, 2026-06-20),
  145536 (x10, 2022-08-17). Adjusted daily moves across these schemes never exceed 2.8%.
- Silver FoF crash (2026-01-30, 2026-02-02) and the 2015 ICICI 120700 jump: flagged LARGE_MOVE, not adjusted.
- 438 LARGE_MOVE events (372 schemes): includes real market moves (COVID 2020, silver 2026). Information
  only; nothing is adjusted.
- 21 TRANSIENT_SHIFT: mostly real reversals (Mar 2020, Jan-Feb 2026). PGIM 138358 (Sep 2019, -30% for
  10 rows) cannot be classed as error or real from this data.
- 13 BAD_VALUE rows are excluded from the adjusted series. Three (quant) fit a glitch pattern (
  reverting to within 0.3% of the prior NAV). Others are gold, silver and Hang Seng Tech fund-of-funds,
  where real volatility could look the same.
  **Real-data precision of BAD_VALUE is UNMEASURED.** The injected test shows recall only.
  Policy: an answer whose window starts or ends on an excluded date must say so.

## Method and honesty notes
- The detector is rules and thresholds. It contains no machine learning. An earlier message called it
  "real machine learning"; that was wrong.
- The injected test was built by the same author as the detector, and one threshold (6%) was set to
  cover the daily moves the generator produces. A 1.00 score shows the detector handles what the
  generator makes, not that it handles every real anomaly. Real-data truth exists for only a few cases.
- Causes are inferred, not confirmed: x100 jumps in liquid funds look like face-value changes, the
  2015 ICICI jump may be a merger, the Jan-Feb 2026 silver falls look real because many silver funds
  moved on the same days. None of this was checked against AMC notices.
- The gold and silver BAD_VALUE rows may be real market days or glitches. Unknown.

## Known limits
- A real persistent move within 6% of a clean ratio (e.g. exact halving) would be adjusted as a unit change.
- Detection thresholds were tuned on this archive; other data would need re-checking.
- Funds in this universe only; stock corporate actions are a separate, unsolved problem.
