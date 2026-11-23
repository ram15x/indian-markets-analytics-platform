# Forecast Lab, experiment 3: market regime detection

**Written before any model was run. Do not change after seeing results; add a dated "Deviations" section instead.**

## Question
Can a hidden Markov model label each trading day as calm, middle or stressed, using only the past, so that the labels really separate what happens next? Descriptive, not a price forecast.

## Data
A daily equity-market composite: the equal-weight average daily log return across the 256 funds of experiments 1 and 2 (same survivorship bias), 2014 onward, using days with at least 100 funds reporting. **Gold and silver are excluded: the RBI series is monthly. USD/INR is excluded: the 2018 to 2022 data hole leaves too little unbroken history.**

## Method
**M: 3-state Gaussian HMM** (hmmlearn, diagonal, 10 random starts, fixed seed) on daily composite returns. States are ordered by fitted variance (0 calm, 1 middle, 2 stressed). Walk-forward: for each test year refit on data before 1 Jan, then label that year's days with the **filtered** probabilities (forward algorithm, past data only). The smoothed output of the library is look-ahead and is not used.
**Trivial rival T:** three groups by the trailing 21-day realised volatility of the composite, cut at the 33rd and 67th percentiles of the training period.

## Outcomes checked (all strictly after the labelled day)
Forward 21-day realised volatility (annualised), forward 21-day return, forward worst drawdown inside the window. Test years 2019 to 2026.

## Pass rule (decided now)
The HMM "works" only if ALL hold: (1) overall forward volatility rises strictly from state 0 to 1 to 2; (2) in at least 75% of test years where two or more states each have at least 10 days, forward volatility is ordered the same way; (3) the stressed-to-calm forward-volatility ratio is at least 1.25; (4) it beats the trivial rival T: a higher stressed-to-calm ratio AND fewer label switches per year. Otherwise it is a negative result and no regime label is shown.

## Not claimed
Labels describe the recent past and what tends to follow on average. They do not predict returns or direction, and one 8-year window with one crash (2020) is a small sample of stressed periods.

---
## Results (run once, protocol unchanged; code `lab/regime_detection.py`, numbers `lab/results/regime_results.json`)
3,166 composite days, test years 2019 to 2026, labels from filtered (past-only) probabilities.

| | HMM state 0 (calm) | 1 (middle) | 2 (stressed) | Trivial rival: low | mid | high trailing vol |
|---|---|---|---|---|---|---|
| Days | 1,189 | 530 | 200 | 659 | 504 | 756 |
| Forward 21-day volatility | 10.9% | 14.1% | 19.9% | 9.4% | 12.5% | 15.7% |
| Forward worst drawdown in window | -3.1% | -4.1% | -5.6% | -2.7% | -3.8% | -4.3% |

Rule checks: (1) strictly rising forward volatility **yes**; (2) ordered in **7 of 8** test years (the exception is 2024, 12.5% vs 11.4%) **yes**; (3) stressed-to-calm ratio **1.83** (needs 1.25) **yes**; (4) beats the trivial rival on a higher ratio **yes (1.83 vs 1.67)** but on fewer label switches **no: 37.6 switches a year against 16.1 for the rival**.

## Verdict: **fails the pre-registered rule, on rule (4).** No regime label is shown by the platform.
The HMM separates future volatility well, and out of sample. Its labels are twitchy: roughly three switches a month, so a calm/stressed tag would flip back and forth. A rival as simple as "trailing volatility in the top, middle or bottom third" is steadier and not far behind.

Caveats that matter:
- **The ratio comparison favours the HMM.** Its stressed group is 10% of days, the rival's top group is 38%. A smaller, more extreme group naturally shows a bigger ratio. Matched group sizes would narrow the gap.
- **Forward returns carry no signal here** (1.1%, 1.2%, 2.1% over 21 days from calm, middle and stressed). Stressed periods followed by rebounds is the usual pattern; one crash year is too little to say more. Nothing is claimed about direction.
- **Gold, silver and USD/INR were not covered** (monthly series, and a data hole).

## What would be a new experiment, not a rewrite of this one
A persistence fix (a minimum number of days before a label may change, or a sticky transition prior) is a sensible next design. It would get its own protocol and its own result.
