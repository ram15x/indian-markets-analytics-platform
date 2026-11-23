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

## More external checks (2026-11-23; scripts/check_published_nippon.py, check_published_axis.py, tests/test_xirr_external.py)
All read from the fund houses' own documents by automated fetch; nothing was tuned to them.
- **Nippon India Small Cap, Direct, product notes as on 31 Jul, 31 Aug, 30 Sep 2026:** 9 of 9 returns (1y, 3y, 5y) match to two
  decimals, 3 of 3 NAVs match to four decimals. Since-inception is withheld by design (the archive's first NAV is later than the
  plan's 1 Jan 2013 inception); the first run used total return for 1y and one row differed by 0.09, so 1y uses actual days/365 like the AMC.
- **Axis Small Cap, Direct, leaflet as on 31 Aug 2026:** 3y and 5y return and all four rupee values (Rs 10,000 grown) match
  exactly. 1y: the Rs value matches exactly (11,547) but our return is 15.47% against a printed 15.38%. 15.47% is what that
  rupee value implies, so the printed percentage looks like a different convention or a leaflet inconsistency; we do not know which.
  Since inception (22.84%, Rs 138,131) matches only when computed from the Rs 10 allotment price on 29 Nov 2013 (Rs 138,130, a Rs 1
  rounding difference); from the archive's first NAV (5 Dec 2013) it is 22.87%. The leaflet rows were unlabelled in the extraction,
  so they were matched by size.
- **XIRR:** both solvers reproduce Microsoft's documented example (0.373362535, tolerance 1e-8) and the lump-sum identity.
  This checks the solver, not the SIP dates used by any particular AMC or app.
Still no outside check for volatility, max drawdown, Sharpe/Sortino, rolling returns, debt funds or Regular plans beyond HDFC.

## Engine C on Windows (2026-11-24)
On the author's Windows machine the existing wheel (imap_engine_c-0.1.0-cp310-abi3-win_amd64) was reinstalled and the full suite run with
`python -m pytest -q -rs`: 280 passed, no skipped tests listed, so the engine-C tests ran and passed there. One machine, one run; not CI.
