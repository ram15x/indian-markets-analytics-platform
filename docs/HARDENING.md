# Hardening: how the checks are checked

Every tool below is here because it found something real or guards something specific. The results are what the tools reported on 2026-11-23, in the sandbox.

## 1. Three independent engines (numpy, DuckDB SQL, Rust)

An answer is shown only if all three implementations produce the same figure. That covers every figure the answer prints, plus the dates it uses.

- **A, numpy:** `src/imap/metrics_a.py`.
- **B, DuckDB SQL plus plain Python:** `src/imap/metrics_b.py`. It builds its own adjusted series in SQL, so the data-quality adjustments are cross-checked too.
- **C, Rust:** `engine_c/`, loaded through PyO3. It was written from the stated conventions, with its own calendar maths and its own XIRR solver (a safeguarded Newton step inside a bracket).

The full run is `scripts/run_agreement_abc.py`. It covers every series (1,772 funds plus gold, silver and USD/INR) and every window (1, 3 and 5 years, and since inception). It covers every measure, including rolling returns and the Sharpe and Sortino ratios.

| Result | Count |
|---|---|
| Verified by A+B+C (values, dates, every printed field) | 40,169 |
| All three agree the figure cannot be computed (mostly Sharpe/Sortino since inception for funds older than the first T-bill rate, Jul 2015) | 1,337 |
| Withheld by rule (monthly series, USD/INR gap, Sharpe on an exchange rate) | 53 |
| Disagreements | **0** |

Mutation testing (below) now includes the Sharpe and Sortino code (run 5).

## 2. Mutation testing (mutmut 3.8.1)

Mutation testing breaks the code on purpose and checks that some test fails each time. A broken copy that no test notices is called a *survivor*; it marks a place where a real bug could go unnoticed.

The scope was the maths and the agreement gate: `metrics_a.py`, `metrics_b.py` and `engine.py`, with about 1,420 broken copies. It ran against the fast tests, which need no data files.

| Round | Caught | Survived | What changed before the round |
|---|---|---|---|
| 1 | 902 of 1,174 checked (77%) | 264 | baseline (the run was cut short) |
| 2 | 1,231 + 9 timeouts of 1,422 (87%) | 182 | gate tests, edge-case tests, and every printed field compared |
| 3 | 1,260 + 8 timeouts of 1,427 (89%) | 159 | engine B's data-quality path, medians, ties and exact boundaries tested |
| 4 | 1,263 + 9 timeouts of 1,431 (89%) | 159 | DuckDB replacement scans turned off; both registration typos now caught |
| 5 | 1,534 + 8 timeouts of 1,746 (88%), with Sharpe/Sortino added | 204 | 38 survivors in the ratio code; tests added for the exact 120-return and 28-day-old-rate limits, zero-variance cases, interior windows and each engine's error messages. 12 ratio survivors remain: error-message wording, `astype(None)` and a table-name case change (all equivalent or cosmetic). Only the ratio code was re-run after the new tests; the other survivors are unchanged from run 4. |

### What mutation testing found in the code itself (not just in the tests)

1. **Printed figures that were never cross-checked.** The answers print several figures besides the headline: the SIP amount invested, the final value and the number of instalments; the start and end NAVs; and the count of daily changes behind volatility. Only the headline figure was compared between engines, so a bug in one of these could have been printed unchecked. Every printed field is now compared. The full run afterwards: 30,787 verified, 0 disagreements.
2. **DuckDB replacement scans.** Engine B's SQL refers to the tables `adj` and `bad`. When a name in a query isn't a registered table, DuckDB looks for a Python variable with that name and reads it instead. The function happens to have local variables named `adj` and `bad`, so a typo in the registration still "worked", reading a different DataFrame. This is now switched off (`SET python_enable_replacements = false`), and a typo makes the tests fail.
3. **Engine B's data-quality path was not covered by the fast tests.** The full run over real data did cover it. A synthetic series with a 10× unit change and a one-day bad NAV now tests it in under a second.

### What survives, and why it is acceptable

These were each read one by one:

- **Newton step for SIP XIRR in engine A (49 survivors).** These break the fast Newton step. Brent's method then takes over and finds the same root, so the answer is unchanged. That is the safety net working.
- **Error-message wording, and SQL keyword case.** DuckDB ignores keyword case, so these change nothing.
- **numpy units.** `np.datetime64(x)` and `np.timedelta64(n)` without a unit, where numpy works out the same unit itself.
- **XIRR bisection details in engine B.** The bracket edge (1000 vs 1001), the iteration cap (300 vs 301), a stopping tolerance of 1e-13 vs 1e-14, and shifting all the cash-flow dates by the same amount. None of these changes the root at the precision that is compared.
- **Strict vs non-strict comparisons** exactly at a tolerance boundary. No real input lands on that boundary exactly.

## 3. Data contracts (pandera 0.36)

`src/imap/contracts.py` holds rules for every table the app loads. They run at start-up, after the manifest check. The manifest proves a file was not changed; the contracts check that its contents make sense:
- no duplicate scheme and date;
- NAVs greater than 0 and below ₹1 crore;
- dates between 2006 and 2100;
- only Direct plans;
- known data-quality event types;
- no adjustment factor of exactly 1;
- metal prices dated on the 1st of the month, in order;
- USD/INR between 30 and 300.

Each rule has a test that feeds bad data and expects a refusal, such as a ×10 decimal slip in a USD/INR rate.

## 4. Static types (mypy 2.3, `check_untyped_defs`)

mypy is clean on all 30 source files, including the bodies of functions without type hints. Fixing its 75 first reports turned up:
- **MCP read-only flags:** they used the old camelCase field names. They only worked through aliases; they now use the proper names.
- **Possible crash on an unexpected message:** a check message that didn't match its expected pattern would have crashed the gold/silver loader with an unclear error. It now raises a clear error.
- **Unhandled empty result:** engine B's SQL single-row reads could return nothing and crash with a TypeError. They now raise the ValueError the gate expects.

## 5. Everything else

- **ruff:** lint (syntax errors, pyflakes, bugbear).
- **pip-audit:** no known vulnerabilities in the pinned dependencies.
- **Property tests (hypothesis):** A and B agree on random series.
- **CI (`.github/workflows/ci.yml`):** runs lint, types, the Rust tests, the engine C build, the audit and the tests. It also builds the Docker image. The data files are not published, so tests that need them are skipped in CI and the skip says why.

## Status

- **Sandbox (Linux, Python 3.13):** 227 tests pass; ruff and mypy are clean; the full run shows 0 disagreements.
- **Not yet built:** the Docker image (Docker Hub is blocked from the sandbox; CI will build it).
- **Not yet built or run on Ram's Windows machine:** engine C.
