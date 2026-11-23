# Metric engine: results (2026-11-22)

Two implementations of each metric, built separately:
- A: numpy over the adjusted series (adjustment applied by `dq.apply`).
- B: DuckDB SQL plus plain-Python date arithmetic and bisection (adjustment re-applied in SQL from
  the raw NAVs, the adjustment table and the bad-value list).
`Engine.compute` returns a number only when A and B agree (relative 1e-9, absolute floor 1e-10,
1e-8 for XIRR); otherwise WITHHELD with the reason. Conventions: docs in `metrics_a.CONVENTIONS`.

Metrics so far: total return, CAGR, max drawdown (with peak/trough dates), annualised volatility
(252-day convention), SIP XIRR (monthly, first NAV on/after the chosen day). Rolling returns are
implemented in both and agree in tests, not yet in the universe run.
Not yet built: Sharpe/Sortino (need a stated risk-free rate), beta, tracking error, capture ratios
(need benchmarks, see ARCHITECTURE.md).

## Known-value tests (tests/test_metrics.py)
Total return and CAGR on a linear series, XIRR of -1000 then +1100 after 365 days = 10%, max drawdown
on a hand-built series, and A vs B on a random walk for every metric. 10 tests pass (with the DQ tests).

## Universe run (scripts/run_agreement.py), 1,772 schemes, windows 1y/3y/5y/inception
| Outcome | Count |
|---|---|
| Both agree, VERIFIED | 27,095 |
| Both agree the metric cannot be computed (funds too new for the window) | 35 |
| Disagreement, WITHHELD | 0 |

One disagreement appeared on the first run: a near-flat fund (149826) with volatility 5.3e-8, where
the two differed by 3e-16. That is floating-point noise, so an absolute floor of 1e-10 was added after
seeing it. It is not a pre-registered threshold.

## What this does and does not show
- Agreement shows the two implementations compute the same thing. It does not show the convention is
  the one a given fund house or website uses (for example 365 vs 252 days, or SIP dates).
- Both share the same list of excluded bad values and the same adjustment decisions. A wrong
  decision in the data-quality layer would not be caught here.
- External check: see the section below (CAGR only, one AMC, one date).

## External check against published figures (scripts/check_published.py)
Source: HDFC AMC performance document dated 31 Oct 2025 (files.hdfcfund.com, ROSHI_JAIN-RP_15.pdf),
Regular Plan Growth: HDFC ELSS Tax Saver, Focused Fund, Flexi Cap. Archive NAVs on 2025-10-31 equal the
published NAVs for all three. CAGR for 1, 3, 5 and 10 years, start dates as printed (Oct 31 / Oct 30):
**12 of 12 match to two decimals** using our convention (365-day compounding, last NAV on or before the
date). A whole-years convention matched only 3 of 12, so the day-count convention matters and ours is
the one HDFC used here.
Limits: one AMC, one date, equity funds, Regular plans, CAGR only. Nothing was tuned to this result (the
convention was fixed earlier). ELSS figures were confirmed against a search excerpt of the PDF; Focused
and Flexi figures come from one automated read of the PDF. Not externally checked: volatility, max
drawdown, SIP XIRR, rolling returns, other AMCs, debt funds, direct plans.

## Property tests (2026-11-23)
Random series with irregular gaps (150 cases): A and B agree on all five metrics. The first run found A's
Newton-only XIRR failing to converge on falling series (B answered); A now falls back to Brent's method.
Universe run after the fix: 27,095 agree, 0 disagree, 35 infeasible (unchanged).
