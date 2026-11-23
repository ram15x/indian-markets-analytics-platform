# Forecast Lab, experiment 1: 21-day volatility forecasts

**Written before any model was run. Do not change after seeing results; add a dated "Deviations" section instead.**

## Question
Can a statistical or ML model forecast a fund's volatility over the next 21 trading days better than simple, well-known baselines?

## Data and universe (fixed rule, applied once)
Cleaned adjusted NAVs from the platform (`series.build_all`). A fund is in if its first NAV is on or before 2014-01-01, its last NAV is on or after 2026-10-01, and its annualised daily volatility since 2015-01-01 is above 8% (drops debt and liquid funds, where volatility is near zero). That gives 256 funds.
**Known bias:** funds that closed or merged before October 2026 are absent (survivorship). This favours neither the models nor the baselines, but absolute levels are not representative of all funds.

## Target
At each forecast origin t (every 21st trading day), RV = sqrt(252 x mean of squared daily log returns over days t+1 .. t+21), using only days after t.

## Methods (information up to and including day t only)
Baselines: **B1** trailing 21-day RV. **B2** trailing 63-day RV. **B3** EWMA (lambda 0.94). **B4 HAR**: pooled linear regression of log RV on log RV5, RV21, RV63 (the standard strong baseline in this literature).
Models: **M1 GARCH(1,1)** with Student-t errors per fund, parameters refit once a year, state filtered to each origin. **M2 LightGBM**, pooled across funds, predicting log RV from RV5/21/63/126, absolute last return, drawdown from 252-day high and 63-day return. Fixed settings, no tuning: 200 trees, learning rate 0.05, 15 leaves, min 200 samples per leaf.

## Protocol
Walk-forward. Test origins from 2019-01-01 to the last origin with a full 21-day future. Models are refit each January on origins whose targets ended before that January (a 21-day purge). Nothing is tuned on test data.

## Scoring
Primary: QLIKE loss on variance (lower is better). Secondary: mean absolute error of volatility. Both reported overall, per test year, and as the share of funds where the model beats HAR.

## Pass rule (decided now)
A model "works" only if ALL hold against HAR, the strongest baseline: (1) lower overall QLIKE; (2) lower QLIKE in at least 6 of the test years; (3) the fund-clustered bootstrap 95% interval for the QLIKE difference excludes zero. Otherwise it is reported as a negative result, and the platform does not show its forecasts.

## Not claimed
No claim about returns. Volatility forecasts say nothing about direction. Results are about this fund set and period, which includes the 2020 crash and 2022 drawdown.

---
## Results (run once, protocol unchanged; code: `lab/vol_forecast.py`, numbers: `lab/results/vol_forecast_results.json`)
256 funds, 23,269 test fund-months, 2019 to 2026. Lower QLIKE is better.

| Method | QLIKE | Volatility MAE |
|---|---|---|
| B1 trailing 21-day | -2.591 | 0.0535 |
| B2 trailing 63-day | -2.535 | 0.0544 |
| B3 EWMA | -2.668 | 0.0511 |
| B4 HAR (reference) | -2.639 | 0.0448 |
| **M1 GARCH(1,1)-t** | **-2.701** | 0.0466 |
| M2 LightGBM | -2.612 | 0.0447 |

**Against the pre-registered rule (vs HAR):**
- **GARCH passes.** Lower overall QLIKE, better in 6 of 8 years, fund-clustered 95% interval for the difference [-0.069, -0.055], and better than HAR for 90% of funds.
- **LightGBM fails.** Worse than HAR on QLIKE (+0.027), better in only 4 of 8 years. Its MAE is about equal to HAR (0.0447 vs 0.0448). **Negative result: its forecasts are not shown.**

## Post-hoc checks (NOT in the pre-registered rule; run because the pass looked cleaner than it should)
`lab/vol_posthoc.py`, `lab/results/vol_posthoc.json`.
1. **The fund-clustered interval is too optimistic.** All funds feel the same market shocks, so 256 funds are not 256 independent tests. Resampling by calendar month instead (94 months), GARCH vs HAR gives [-0.146, -0.001]: it only just excludes zero, and GARCH is better than HAR in only 50% of months.
2. **GARCH vs the simple EWMA is not significant.** The EWMA baseline (B3) actually beats HAR on average. GARCH vs EWMA: difference -0.033, month-block interval [-0.081, +0.021], better in 57% of months. The rule named HAR the strongest baseline in advance; on this data that was wrong, and the fair comparison is EWMA.
3. **Part of GARCH's edge is in stressed periods.** Excluding 2020, GARCH still has the lowest QLIKE (-2.916) but the gaps shrink. In calm periods (prior volatility below median) it leads by about 0.03; in stressed periods it leads EWMA slightly and LightGBM is clearly worst.

## Verdict
GARCH(1,1)-t is the best method of those tested, but the margin over a simple EWMA is small and not statistically reliable month to month. The honest claim is "GARCH was best on average in this back-test and passed the rule; it is not clearly better than EWMA". LightGBM did not help. No claim about any fund's future.

## Deviations and later notes
- 2026-11-23: GARCH(1,1)-t passed the pre-registered rule, so the platform may show it. It is shown only as an opt-in "Volatility estimate (model)" next to a fund's verified answer, labelled as not verified, with the EWMA and last-21-day figures beside it and the post-hoc caveats above stated. It is offered only for funds the Lab tested (daily series, at least 750 returns, volatility above 8% a year). LightGBM remains hidden. Code: `src/imap/estimate.py`.
