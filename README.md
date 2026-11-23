# Indian Markets Analytics Platform

An AI analyst for Indian mutual funds, gold, silver and USD/INR where **every number is computed by code, cross-checked by independent implementations, and verified, or the answer is withheld.** The language model only plans; it never writes a figure. Nothing here is investment advice, and nothing predicts.

> A personal project. Evidence for each claim is in `docs/`; items marked UNVERIFIED have not been proven.

## Try it in two minutes (no data needed)
    pip install -r requirements.txt
    python serve.py --demo          # then open http://127.0.0.1:8765

Demo mode runs on **invented** data (a banner says so on every page), so anyone can see the idea working: ask a question, watch both engines agree, and watch an unsupported question get withheld with the reason. The real data is built locally by the pipeline (see Data); this repository does not ship it.

![Demo: a verified answer, a withheld answer, and a screener](docs/demo.gif)

## What you can do
- **Ask** in plain words: total return, CAGR, max drawdown, volatility, SIP XIRR, rolling returns, Sharpe and Sortino, for 1,772 mutual-fund schemes (AMFI), gold and silver (RBI monthly), USD/INR.
- **Screen** funds by name, ranked by one measure, with the category median, "beats x%" per row, a survivorship-bias note, and a CSV download.
- **Calculate a SIP** and **compare** funds, gold, silver and the dollar on one shared period.
- **Learn:** every answer has a "Numbers behind this answer" panel (formula, start and end NAV, days, engines) and a plain-words reading. A Learn panel explains CAGR vs total return, NAV, Direct vs Regular, drawdown, XIRR, Sharpe, survivorship bias and more, at three levels. The text is fixed and versioned, not written by a model.
- Use it from **Claude Desktop** through MCP (`docs/MCP.md`), or read your own CAS statement (in memory only).

It describes past figures to help you understand them. It gives no advice and no forecasts.

## How it works
```
question -> planner (LLM or rules) -> plan (JSON) -> validator (years/amounts must come from the question)
         -> resolve fund -> engine A (numpy) + engine B (DuckDB) [+ engine C (Rust)] -> compare every printed field
         -> VERIFIED answer   or   WITHHELD with a reason
```
The language model only plans; it never writes a figure. Data checks run first: SHA-256 manifest (the app refuses to start on a mismatch), pandera schemas, NAV outlier and scale-change detection with an audit trail.

## Evidence, and what it does not show
- **Engines agree:** 40,169 figures verified by all engines, 0 disagreements (`docs/HARDENING.md`). Agreement shows the arithmetic is consistent, not that the definition or the data is right.
- **Checked against fund houses' own documents:** CAGR matches HDFC 12/12, Nippon India 9/9 (plus 3/3 NAVs), Axis 3 of 4 returns (all 4 rupee values match; the 1y percentage differs by 0.09). XIRR solver matches a documented example. Volatility is consistent with one factsheet figure (9.90% vs 9.93%, one fund, secondary source) and Sharpe is close (0.775 vs 0.80, risk-free rate unknown); drawdown and Sortino have no outside check. Details: `docs/ENGINE_RESULTS.md`.
- **Tests:** 280, plus ruff, mypy and pip-audit clean; mutation testing caught 88% of 1,746 mutants and found two real bugs. CI runs only the tests that do not need the real data (about half); the rest run locally.
- **Planner evaluations** on locked sets, failures kept on record: `docs/PLANNER_EVAL_V3.md`, `docs/PLANNER_EVAL_V4.md`. Experimental forecasting models: `docs/LAB.md` (mostly negative results).

## Known limits
- Survivorship bias: only funds still running (active Direct Growth plans) are in the data. No benchmark index data (not redistributable); peers are compared among funds with matching names, not official categories.
- Gold and silver are RBI monthly averages ending months before fund NAVs; volatility and SIP are withheld for them. USD/INR has a gap from July 2018 to April 2022. Sharpe/Sortino start July 2015.
- Engine C (Rust): tests pass on Linux and on the author's Windows machine (one run, 280 passed, `docs/ENGINE_RESULTS.md`); CI does not build it.
- Reuse terms for AMFI-derived data are UNVERIFIED (`docs/FEASIBILITY.md`); NSE data must not be published; FBIL data is not used.
- Full status list: `docs/STATUS.md`. Also a Dockerfile (image not yet built outside CI).

## Data
Built locally from the AMFI NAV archive and RBI sources (Handbook, reference rate archive, T-bill yields). `python -m pytest -q` runs everything when the data is present.
