# Indian Markets Analytics Platform

An AI analyst for Indian mutual funds, gold, silver and USD/INR where **every number is computed by code, cross-checked by independent implementations, and verified, or the answer is withheld.** The language model only plans; it never writes a figure. Nothing here is investment advice, and nothing predicts.

> Status: working locally; not yet published. Evidence for each claim is in `docs/`. Items marked UNVERIFIED have not been proven.

## Why it is different
| Most finance chatbots | This project |
|---|---|
| The model writes the numbers | Code computes them; the model only turns a question into a plan |
| One implementation | Two independent engines (numpy; DuckDB SQL) plus an optional Rust engine, which must agree on values and dates |
| Wrong answers look confident | Disagreement, a data gap or a short window means the answer is **withheld with the reason** |
| "Trust me" | Hand-checked figures, mutation testing, pre-registered model evaluations |

## What it answers
Total return, CAGR, max drawdown, volatility, SIP XIRR, rolling returns, **Sharpe and Sortino ratios** (risk-free rate from RBI 91-day T-bill yields), for 1,772 mutual-fund schemes (AMFI NAVs), Mumbai gold and silver (RBI), and USD/INR (RBI). Compare several in one question. Optional: read your own CAS statement (in memory only).

## How it works
```
question -> planner (LLM or rules) -> plan (JSON) -> validator (years/amounts must come from the question)
         -> resolve fund -> engine A (numpy) + engine B (DuckDB) [+ engine C (Rust)] -> compare every printed field
         -> VERIFIED answer   or   WITHHELD with a reason
```
Data checks run first: a manifest of SHA-256 hashes (the app refuses to start on a mismatch), pandera schemas, NAV outlier and scale-change detection with a recorded audit trail.

## Evidence
- **Three-engine agreement** over every series and window: 40,169 figures verified by all engines, 0 disagreements (`docs/ENGINE_RESULTS.md`, `scripts/run_agreement_abc.py`).
- **Tests:** 241, plus ruff and mypy clean, pip-audit clean.
- **Mutation testing** on the maths and the agreement gate: 88% of 1,746 mutants caught; it found two real bugs (`docs/HARDENING.md`).
- **Published-figure check:** HDFC CAGR matches 12 of 12 published figures (`docs/ENGINE_RESULTS.md`).
- **Planner evaluations:** locked sets, with failures kept on record. A first test of gold, silver and USD/INR questions failed (14 of 21), the prompt was fixed, and a new held-out set passed (15 of 17, 0 wrong answers): `docs/PLANNER_EVAL_V3.md`, `docs/PLANNER_EVAL_V4.md`.
- **Forecast Lab:** four pre-registered model experiments; one modest pass, three honest failures: `docs/LAB.md`.

## Quick start
    pip install -r requirements.txt
    python -m pytest -q
    cd src && python -m imap.server        # then open http://127.0.0.1:8765
A Groq key can be pasted on the page (kept in memory only); without one a scripted parser reads questions. Also: an **MCP server** for Claude Desktop (`docs/MCP.md`) and a Dockerfile (`docs/ARCHITECTURE.md`; the image has not been built yet, so CI will be its first build: UNVERIFIED).

## Data
Built locally by the pipeline; sources: AMFI NAV archive, RBI (Handbook, reference rate archive, T-bill yields), optional NSE prices for personal use. **Reuse terms for AMFI-derived data are UNVERIFIED (`docs/FEASIBILITY.md`), and NSE data must not be published, so the repository does not include data files.** FBIL data is not used (its terms bar commercial use without permission).

## Known limits
- USD/INR has a hole from July 2018 to April 2022, so long dollar-rupee windows are withheld.
- Gold and silver are RBI monthly averages and end earlier than fund NAVs, so volatility and SIP are withheld for them, and comparisons across different end dates are refused.
- Sharpe and Sortino need T-bill yields, which start July 2015 and run about two months behind; those ratios are withheld before then and capped at the latest published yield.
- Engine C (Rust) has been built and tested only in the development sandbox; on Windows it is untested.
- Every claim above has a source in `docs/`; the full status list is `docs/STATUS.md`.

## Licence
MIT for the code and documents (`LICENSE`). Third-party data is not included and keeps its owners' terms.
