# Forecast Lab, experiment 2: calibrated 1-year return ranges

**Written before any model was run. Do not change after seeing results; add a dated "Deviations" section instead.**

## Question
Can we give an 80% range for a fund's next-1-year log return that is (a) actually right about 80% of the time and (b) narrower than simple alternatives? This is a range, not a point forecast and not a direction call.

## Data
The same 256-fund universe as experiment 1 (same survivorship bias). Origins every 21 trading days from day 252. Target: log return over the next 252 trading days, which must be fully observed. Test origins from 2019-01-01 to the last with a full year ahead (late 2025).

## Methods (information up to the origin only)
Baselines: **B1** pooled empirical 10th and 90th percentiles of past 1-year returns across all funds. **B2** each fund's own past percentiles (needs 24+ past origins, else B1). **B3** volatility-scaled: percentiles of past (return / EWMA volatility), times today's EWMA volatility.
Model: **M1 conformalised quantile LightGBM.** Pooled LightGBM quantile regressions (10% and 90%) on RV21/63/126, EWMA vol, drawdown, 63- and 252-day momentum, then split-conformal widening (CQR) using a calibration set. Fixed settings, no tuning: 150 trees, learning rate 0.05, 15 leaves, min 200 samples per leaf.

## Protocol (no leakage)
For test year Y: models fit on origins whose targets ended before 1 Jan (Y-1); the calibration set is origins whose targets ended between 1 Jan (Y-1) and 1 Jan Y; baselines use both sets. Walk-forward, refit each year.

## Scoring
Coverage (share of actual returns inside the range), average width, and the interval score at 80% (width plus a penalty of 10x the miss distance; lower is better). Reported overall, per year, and for calm vs stressed prior volatility.

## Pass rule (decided now)
M1 "works" only if ALL hold: (1) overall coverage between 77% and 83%; (2) coverage between 70% and 90% in at least 5 of the 7 test years; (3) lower mean interval score than every baseline, with a **calendar-month block bootstrap** 95% interval for the difference against the best baseline that excludes zero (funds share market shocks, so funds are not independent; lesson from experiment 1). Otherwise it is a negative result and the platform does not show these ranges.

## Not claimed
Origins every 21 days with 252-day targets overlap heavily, so the effective number of independent years is small (about 7). No claim about any future period. A range is not advice and not a promise.

---
## Results (run once, protocol unchanged; code `lab/range_forecast.py`, numbers `lab/results/range_forecast_results.json`)
256 funds, 20,453 test fund-origins, test years 2019 to 2025. Target coverage 80%.

| Method | Coverage | Width | Interval score (lower is better) |
|---|---|---|---|
| B1 pooled percentiles | 77.4% | 0.431 | **0.726** |
| B2 per-fund percentiles | 74.5% | 0.419 | 0.756 |
| B3 volatility-scaled | 75.1% | 0.473 | 0.755 |
| M1 conformal quantile LightGBM | 72.3% | 0.452 | 0.781 |

Coverage by test year (target 80%): B1 63, 29, 91, 98, 77, 95, 91 (2019 to 2025). M1: 58, 76, 98, 98, **16**, 63, 98.

## Verdict: **negative result. M1 fails the rule** (overall coverage 72.3%, outside 77 to 83%; coverage inside 70 to 90% in only 1 of 7 years; its interval score is worse than the best baseline, difference +0.068, month-block 95% interval [-0.039, +0.168]).
The platform does **not** show 1-year return ranges.

What the experiment shows:
- **No method was reliably calibrated.** Coverage swung between about 15% and 98% depending on the year, for every method. The simple pooled percentiles came closest overall (77.4%) but covered only 29% in 2020.
- **Calibration data from the past year was the wrong guide.** The conformal step learns the width from the previous year. After the 2020 crash and rebound, the next year's returns looked nothing like it, so the widening pointed the wrong way. 2023 (coverage 16% for M1) is the clearest case.
- **It is not that the model is bad at width.** M1 had the best interval score in 2020 and 2024. The failure is year-to-year instability, which a 7-year sample (with heavily overlapping origins) cannot average away.
- **Caveats:** one seven-year window in a mostly rising market, survivorship in the fund set, and fixed untuned settings. A different design could do better; this one did not.
