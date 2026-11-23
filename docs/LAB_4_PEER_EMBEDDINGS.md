# Forecast Lab, experiment 4: fund embeddings for peer matching

**Written before any model was run. Do not change after seeing results; add a dated "Deviations" section instead.**

## Question
Can a small transformer, trained without labels on fund return histories, place funds so that a fund's nearest neighbours are genuinely similar funds (same SEBI-style category) better than simple, standard similarity measures? A peer finder, not a forecast.

## Ground truth (independent of every method)
Category read from the **scheme name** with fixed keyword rules (large cap, mid cap, small cap, flexi cap, multi cap, large and mid cap, ELSS, focused, value/contra, liquid, overnight, ultra short, short duration, corporate bond, gilt, gold, and a few more; list in `lab/embedding_peers.py`). A fund is labelled only if exactly one rule fires. Direct-plan growth schemes only. Funds with no label are used as nobody's neighbour. Names are noisy ground truth: nothing is claimed beyond "agrees with the category in the name".

## Data and windows (fixed now)
Adjusted daily NAV returns. **Training window** 2015-01-01 to 2019-10-31 (the transformer only ever sees this). **Window A** 2019-11-22 to 2022-11-21. **Window B** 2022-11-22 to 2025-11-21, the main evaluation window and fully after training. A fund needs data on at least 98% of a window's days to be included in it.

## Methods
- **N: contrastive transformer.** Daily returns in 5-day patches, 2 layers, width 64, mean-pooled; trained with InfoNCE where two non-overlapping 250-day crops of the same fund are a positive pair and other funds are negatives. 600 steps, batch 128, fixed seed and settings, no tuning.
- **N0 control:** the same network with random untrained weights.
- **CORR:** nearest by Pearson correlation of daily returns.
- **FEAT:** standardised vector of volatility, beta to the composite, correlation to the composite, skew, excess kurtosis, max drawdown, downside deviation.
- **PCA:** first 16 principal components of the standardised return series.

## Scoring
Precision at 5: for each labelled fund in window B, the share of its 5 nearest labelled funds (excluding funds with the same base name) that share its category. Overall and per category group; fund-level bootstrap 95% intervals. **Stability:** overlap between a fund's top 5 in window A and window B, among funds present in both.

## Pass rule (decided now)
N "works" only if ALL hold: (1) its precision at 5 beats the best of CORR, FEAT, PCA by at least 0.03, with a paired fund-bootstrap 95% interval for the difference that excludes zero; (2) it beats the random-weights control N0; (3) its stability is at least that of the best baseline on precision. Otherwise it is a negative result and is not shown.

## Not claimed
Peer similarity in returns is not similarity in holdings, risk of loss, or future performance. One training window, one seed.

---
## Deviation (before any valid result)
The first run crashed with no output: the trading-calendar filter I wrote (days when at least half of all funds report) left only 204 training days. I changed it to "days when at least 100 funds report", the filter used in experiment 3. This is an implementation fix; no rule, method or threshold was changed, and no result had been seen.

## Results (run once; code `lab/embedding_peers.py`, numbers `lab/results/embedding_results.json`)
477 labelled funds in window B, 335 in window A (333 in both), 328 in training. 28 categories, 20 with at least 5 funds.

| Method | Precision at 5 | Top-5 stability, A vs B |
|---|---|---|
| CORR (return correlation) | 58.3% | **33.0%** |
| FEAT (risk features) | 48.6% | 13.5% |
| PCA (16 components) | **59.2%** | 23.8% |
| N0 (transformer, random weights) | 53.6% | 14.3% |
| **N (transformer, trained)** | 54.0% | 16.0% |

## Verdict: **negative result. The trained transformer fails the rule.**
- Against the best baseline (PCA): -5.2 points, bootstrap 95% interval [-8.4, -2.2]. It is *worse*, not just not better.
- Against the random-weights control: +0.4 points, interval [-2.0, +2.8]. **Training did nothing measurable.** The untrained network is as good, so the 54% comes from the architecture's random projection, not from anything learned.
- Stability: every method is poor, and the trained network is below plain correlation (16% vs 33%).

Why it probably failed (not tested; do not read these as findings):
- Only 328 funds and 4.8 years to learn from, 600 training steps, no tuning. A larger, longer run might learn something. This one did not.
- Many funds in a category hold nearly the same stocks, so "other funds are negatives" in the contrastive loss penalises the very neighbours we want.
- Name-based categories are noisy ground truth, which caps every method.

What the experiment does show: **plain correlation of daily returns already finds a same-category peer about 58% of the time in the top 5, with no machine learning**, and it is the most stable. Per-category scores vary widely (near 100% for overnight, gold and pharma funds; 6 to 20% for flexi cap, focused and value funds, which really are mixed).
