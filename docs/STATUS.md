# Status ledger

Rule: a feature is "done" only with a test or measurement named here. Labels: MEASURED (we ran it),
SOURCED (a cited page said it), INFERRED (our reading, not confirmed), UNVERIFIED, NOT BUILT.
Update this file in the same step as the work. If a claim has no evidence pointer, it is not a claim.

Last updated: 2026-11-23

## Built
| Item | Label | Evidence |
|---|---|---|
| Universe: 1,772 active Direct+Growth schemes, 2,978,587 NAV rows | MEASURED | scripts via loader.py, data/schemes.parquet |
| Scale-change detection and adjustment (rules, no ML) | MEASURED on injected anomalies; 4 real cases checked | docs/DQ_RESULTS.md, data/dq_eval_locked.json |
| Bad-value exclusion (13 real rows) | recall MEASURED on injected only; real precision UNVERIFIED | docs/DQ_RESULTS.md |
| Metric engine: total return, CAGR, max drawdown, volatility, SIP XIRR; two implementations agree | MEASURED (27,095 agree, 0 disagree); CAGR matches HDFC published figures 12/12 at 2dp (one AMC, one date); other metrics UNVERIFIED externally | docs/ENGINE_RESULTS.md |
| Fund-name resolution v1 | Pre-registered scores MEASURED on generated queries (locked: 0 confident-wrong, 97% typo coverage). **Unsafe for renamed/old names** (found afterwards in an unscored demo) | docs/RESOLVE_RESULTS.md |
| Fund-name resolution v2 (AMC required, former names, coverage rule) | MEASURED on generated queries: locked 0 wrong-resolved, typo coverage 100%; **4 of 5 regression queries pass** ("hdfc nifty 50 index" still resolves to Nifty Next 50). Rename test not held out; only 10 sourced + 27 in-archive renames known | docs/RESOLVE_V2_RESULTS.md |
| Planner pipeline: plan schema + validator, code-only executor, answer renderer | MEASURED: 13 malformed/hostile plans rejected in tests; end-to-end tests on real data | tests/test_planner.py, src/imap/plan.py |
| Stand-in planner (regex, not a model) | MEASURED on 24 pre-registered questions: 17 correct, 0 wrong answers, 7 safe misses | docs/PLANNER_EVAL.md, data/planner_eval_rule-stand-in.json |
| Model planner, gpt-oss-120b on Groq | MEASURED: **FAILED** pre-registered bars (19 correct / 3 wrong as scripted; scorer bug found afterwards, see doc) | docs/MODEL_RUN_1.md |
| Explainer checker (placeholders only; rejects digits, fund-house words, advice, comparison, direction words) | MEASURED with scripted texts: 12 bad texts rejected, good text filled | tests/test_explain.py |
| Explainer, gpt-oss-120b | MEASURED: **FAILED** (1 of 10 accepted; checker too strict; direction placeholder misleads) | docs/MODEL_RUN_1.md |
| Fund-name resolution v3 (short-name rule) | MEASURED on a fresh locked split: 0 wrong resolves, short-query coverage 92%, "axis elss"/"parag parikh elss" fixed; "hdfc nifty 50 index" still fails | docs/RESOLVE_EVAL.md (v3), data/resolve_v3_eval_locked.json |
| Planner v2 (ask step, advice/prediction notice, code guards on years/SIP amount/day) and code-written result sentences | MEASURED in unit tests; stand-in on the new 30-question set: 16 correct / 0 wrong / 14 safe misses (reference only) | docs/PLANNER_EVAL_V2.md, tests/ |
| Planner v2, gpt-oss-120b | MEASURED: **PASSED** pre-registered bars, 29 correct / 0 wrong / 1 safe miss (30 questions, one author; see caveats) | docs/MODEL_RUN_2.md |
| Explainer v2, gpt-oss-120b | MEASURED: **FAILED** (3 of 16 accepted). Reading the texts: several model definitions are factually wrong for growth-option NAVs and XIRR | docs/MODEL_RUN_2.md |
| Explanations: fixed glossary (data/glossary.json), shown under code-written results | BUILT; covers all 5 metrics (test). Text reviewed and approved by Ram (2026-11-23, no changes) | data/glossary.json, src/imap/explain.py |
| Local web page (127.0.0.1 only; key per request, never stored; click to choose a fund or measure) | MEASURED: API tests incl. key never echoed and no browser storage; screenshots checked desktop + mobile. Not tested with a real key in the browser yet | src/imap/server.py, src/imap/web/index.html, tests/test_server.py |
| Local server hardening: Host/Origin checks, required client header, CORS preflight refused, security headers (CSP, no framing) | MEASURED in tests (cross-site, DNS-rebinding, preflight cases) | tests/test_server.py |
| Groww read-only stock holdings (cost basis only; free plan has no prices; MFs not in this API) | MEASURED against a fixture built from Groww's documented fields; source scan forbids order/write calls. **Not run against the real Groww API yet** | src/imap/portfolio/groww.py, tests/test_groww.py |
| Nightly refresh from AMFI NAVAll.txt with 9 gates; atomic write + backup; report per run | MEASURED on synthetic files and on the REAL file (2026-11-23): first real run was correctly REFUSED because AMFI changed to an 8-column layout; parser now reads both layouts by header; re-check on the real file: all 9 gates pass, 1,772/1,772 schemes present, latest NAVs identical to the archive (0 conflicts) | docs/REFRESH.md, tests/test_refresh.py |
| Property tests: A vs B agree on 150 random irregular series incl. SIP XIRR; validator fuzzed with 400 junk plans | MEASURED. Found a real bug (below) | tests/test_properties.py |
| Pinned versions + CI workflow (not pushed) | Lock = Ram's machine versions; CI not run (no repo yet) | requirements-lock.txt, .github/workflows/ci.yml |
| Tracking charts under answers (indexed growth, fall from peak, SIP value vs invested; crosshair tooltip, table view, flagged dates marked) | MEASURED: chart end points reproduce the verified figures (tests); palette validated (colour-blind safe, 3 series); screenshots desktop + mobile checked | src/imap/charts.py, tests/test_charts.py |
| Data manifest (SHA-256 of every trusted data file; app refuses to start on mismatch; refresh rewrites it) | MEASURED (tamper and missing-manifest tests) | src/imap/manifest.py, data/MANIFEST.json |
| External truth as a permanent test: 12 HDFC published CAGR figures, both implementations | MEASURED (12/12 at 2dp, fixture of 114 NAV rows) | tests/test_published_figures.py |
| Server catch-all (plain 500, no internals or request body in the response) | MEASURED | tests/test_server.py |
| Lint (ruff: pyflakes + bugbear) and dependency audit (pip-audit) | ruff clean; pip-audit: no known vulnerabilities in requirements-lock.txt (2026-11-23) | pyproject.toml |
| CAS import: your MF holdings, net invested, value and XIRR (per scheme + portfolio, two implementations); in memory only; no personal details in output; withholds on unit/value mismatches, pre-period holdings, gifts and other unvaluable lines | MEASURED on fixtures that validate against casparser's own data model, incl. a hand-checked 10% case. **Not run on a real CAS PDF yet** | src/imap/portfolio/cas.py, tests/test_cas.py |
| Stock holdings value: NSE end-of-day closes (5 checks; refuses unknown headers) matched to Groww holdings by ISIN; value and gain vs average buy price | MEASURED on fixtures (new and old header names, 4 refusal cases, valuation maths). URL and column names VERIFIED on Ram's first real run (2026-11-23: 3,742 rows, 2,760 EQ, trade date 2026-11-20, all checks passed); local personal use only | src/imap/prices.py, tests/test_prices.py, docs/PRICES.md |
| Tests | MEASURED | tests/ (142 pass in the sandbox AND on Ram's Windows machine, 2026-11-23) |

## Not built
Resolver tests on real user phrasing, hosting, scheduled refresh (needs Ram to run schtasks), back-fill of missed days, charts for stocks (needs a price source),
Sharpe/Sortino, beta, tracking error, capture ratios, rolling-return universe run, news lane,
gold/silver, FX, stocks, documents, any ML.

## Open questions (all UNVERIFIED)
- CAS: whether stamp duty, STT and TDS appear as separate lines in Ram's statement as casparser models them; checked on the first real statement.
- May data/*.parquet (derived from AMFI NAVs) be published in a public GitHub repo? Decide before the first push; CI needs it.
- Reuse terms for the AMFI archive, mfapi.in, NSE data.
- A free daily INR gold/silver source.
- Whether our conventions for volatility (252 days), SIP dates and drawdown match published figures. (CAGR 365-day convention: checked, HDFC only.)
- Real causes of the flagged jumps (face-value changes, mergers, real vs glitch).
- A split/bonus source for NSE 500.

- Complete rename list (we have 10 sourced + 27 in-archive; others unknown).

## Corrections log
- 2026-11-23: refresh crashed instead of refusing cleanly on an unknown file layout (empty table had the wrong date type); found by a test while adding the new AMFI layout; fixed.
- 2026-11-23: property test found that implementation A's SIP XIRR (Newton only) failed to converge on some falling series while B answered; the app would have withheld those answers. Fixed with a Brent fallback (scipy). The first regression test written for it did not reproduce the failure (checked against the old code); replaced with inputs that do. Full-universe agreement re-run: unchanged (27,095 agree, 0 disagree).
- 2026-11-23: explainer v2 harness resolved test funds by full name and crashed; fixed to pass scheme codes. Renderer showed an empty 'Matched' line for resolve-only advice plans; fixed after run 2 (scores unchanged).
- 2026-11-23: planner scorer did not implement the written NOFACT rule; found after the first model run; result kept as FAILED. Model name llama-3.3-70b-versatile was written from memory and did not exist on Groq.
- 2026-11-23: v2 fixes the old-name failures it was tested on but keeps one known failure ("hdfc nifty 50 index"). Resolver output must always be shown to the user for confirmation.
- 2026-11-23: resolver v1 locked scores looked clean but a hand-written demo showed confident wrong matches on renamed funds; v1 must not be wired to answers without showing the matched name and asking to confirm.
- 2026-11-22: "1,799 schemes" was wrong (included Bonus/IDCW options); correct is 1,772.
- 2026-11-22: DQ layer was called "ML"; it is rules and thresholds.
- 2026-11-22: "near-certain glitches" softened; causes of flagged events are inferred.

## 2026-11-23: rolling returns, gold, silver, USD/INR (sandbox; 162 tests pass there, NOT yet run on the Windows machine)

Rolling returns: every 1/3/5-year rolling figure over the universe computed by both engines: 3,652 verified, 0 disagree.
The glossary entry for rolling returns is new and has not been reviewed by Ram.

Gold and silver: RBI Handbook tables 162, 163, 164 (monthly averages, Mumbai; Apr 2017 to Apr 2026, 109 months, none missing).
- Checked: every fiscal-year Average row equals the mean of its months (0 mismatches); spread = local minus foreign price, row by row;
  overlapping months across editions.
- Found: Table 163 prints the Mumbai silver price in the silver spread column for Jul 2024 to Jun 2025 (12 months). Table 164 corrects it.
  The editions agree on every price; they disagree only on that spread. Newest edition is used.
- Found: Table 162, Jul 2019, gold spread is Rs 10 off (0.03%). London leg checked (gold- and silver-implied USD/INR agree);
  which column is the misprint cannot be settled. Recorded in data/macro_notes.csv; any new unlisted inconsistency stops the build.
- Monthly averages: volatility and SIP are withheld (they need daily prices). Answers say "monthly average" and the latest month.
USD/INR: RBI reference-rate archive, 2,447 days, 2013-01-01 to 2026-11-20. No rates from 2018-07-24 to 2022-04-12 (FBIL era)
  and a 15-day gap in Jul 2018. Any measure whose window overlaps a gap is withheld; rolling periods start after the last gap.
- "gold", "silver", "usd inr" are exact phrases; any question that says fund/ETF/FoF goes to the fund resolver.
- UNVERIFIED: how the Groq model plans gold/silver/USD questions (planner prompt unchanged; the locked eval did not cover them).
- Not checked against an outside source: the gold/silver levels themselves (they are RBI's published figures).
- Correction 2026-11-23: the stand-in planner kept "total" from "total return" in the fund text (old bug, found while testing silver); fixed.
- Correction 2026-11-23: the stand-in drops the word "fund", so "gold fund" briefly resolved to the gold price; caught by an existing test; the question text is now checked too.

## 2026-11-23 (later): MCP server, engine C (Rust), hardening, Docker/CI. Sandbox results; NOT yet run on the Windows machine

- **MCP server** (`python mcp_server.py`, stdio, read-only): find_fund / compute / answer_question + 3 resources. Real stdio round
  trip tested (mcp 2.3.0). Found and fixed while building it: a comparison of gold (data to Apr 2026) with a fund (to Nov 2026)
  ranked two different periods. Comparisons are now withheld when start or end dates differ by more than 7 days (web page too).
- **Engine C (Rust, PyO3)**: third independent implementation. Full run over every series and window, values + dates + every
  printed field: 30,787 verified by A+B+C, 0 disagreements. Optional: without it the app runs on A+B and says so.
- **Mutation testing (mutmut)** on the maths and the gate: 89% of 1,431 broken copies caught (from 77%). It found two real
  problems: printed figures (SIP invested/final value/instalments, NAVs, counts) were not cross-checked between engines; and
  DuckDB "replacement scans" let a mistyped table name silently read a different Python variable. Both fixed. Survivors reviewed
  one by one (docs/HARDENING.md).
- **Data contracts (pandera)** checked at start-up after the manifest. **mypy** clean incl. untyped function bodies.
- **Docker + GitHub Actions CI** written; NOT built (Docker Hub blocked in the sandbox). CI will build it on the first push.
- Tests: 227 pass in the sandbox. Tests needing the unpublished data are marked and skipped in CI with the reason.

## 2026-11-23 (later still): Sharpe and Sortino ratios, on RBI 91-day T-bill yields

- **Risk-free rate:** RBI's 91-day T-bill auction cut-off yields.
  - Sources: 11 Handbook editions (Jul 2015 to Jun 2026), plus the Sep and Oct 2026 Bulletins for Jul and Aug 2026. In total 573 auctions, Jul 2015 to 27 Aug 2026.
  - Every row is checked: the printed yield must match the yield implied by its own cut-off price, (100/p - 1) x 365/91, within 0.03 percentage points. All 573 pass.
  - The editions agree on every date where they overlap.
  - Five auctions had no yield printed (no bids accepted); they are skipped and listed.
- **A trap in RBI's August 2026 Bulletin file:** Excel stored "June 3" as 1 June 2003, putting the day in the year. These dates are decoded and flagged. The four decoded June dates match the Handbook exactly, which confirms the decoding.
- **Conventions:**
  - Daily excess return = NAV return minus yield x days / 365 (simple, actual/365, as RBI quotes it). The rate used is from the last auction on or before the previous NAV date, at most 28 days old; the longest gap between auctions is 22 days.
  - Sharpe = mean / stdev of the excess returns, times sqrt(252). Sortino = mean / downside deviation, times sqrt(252). At least 120 daily returns.
  - Withheld for monthly series (gold, silver) and for USD/INR.
- **Period:** it ends at the last published T-bill week plus 7 days and keeps the length asked for. For example, "3 years" currently runs to 3 Sep 2026, not to the latest NAV. The answer says so in a note, because RBI publishes these yields about two months late.
- **Results:** all three engines (numpy, DuckDB SQL with an ASOF join, Rust) agree on every Sharpe and Sortino figure. The full run is now 40,169 verified, 0 disagreements.
- **Not done yet:**
  - Mutation testing of the new code.
  - The ChatPlanner prompt lists the two new measures, but the model's planning of them has not been evaluated.
  - The glossary entries for both (v2026-11-23c) have not been reviewed by Ram.
- Correction 2026-11-23: on Windows the gold/silver and T-bill loaders listed every Excel file twice ('*.XLSX' and '*.xlsx' match the same files when names ignore case). Answers were unaffected (identical copies merge) but the build report double-counted. Found by test_real_tables_parse_and_cross_check on Ram's machine; fixed with one case-insensitive listing, plus a test.
- 2026-11-23 09:47: Ram's Windows machine: 227 passed, 9 skipped, 0 failed (engine C not built there; skips not yet itemised; 9 warnings not yet reviewed).
- 2026-11-23: all 9 skips on Ram's machine are engine C (not built). Warnings fixed: openpyxl read-only workbooks were never closed (on Windows an open file is locked); DataFrame.join lsuffix/rsuffix (deprecated in pandas 4) replaced with add_suffix; a test server socket was left open. Sandbox: 236 passed, 0 warnings.

## 2026-11-23 (decision): Docker dropped
The Dockerfile and .dockerignore were never built, so they are git-ignored and the CI docker job was removed. Everything else in CI is unchanged.

## 2026-11-23 (night): SIP calculator panel
- New panel on the page: fund, monthly amount, day, period. It builds an ordinary question, so the same plan validator and both engines run; nothing new computes a figure. Backward-looking only; it is not a forecast.
- Fixed a gap in the scripted planner: "SIP of 10000" and "10000 sip" were not read as amounts, so the validator rejected them (safe, but unhelpful). A SIP question with no amount now leaves it out, and the answer says the amount was assumed.
- MEASURED: 252 tests pass in the sandbox (2 new), ruff and mypy clean; panel checked in a headless browser (Rs 10,000 on the 7th for 7 years: 84 instalments, Rs 8,40,000 invested, XIRR 16.67%, chart agrees with the card). NOT yet checked in Chrome on the Windows machine.

## 2026-11-23 (night, later): shared-window comparison
- New panel and endpoint (`/api/common`, `src/imap/common.py`): compare 2 to 3 assets (funds, gold, silver, USD/INR) over ONE shared period. Gold and silver (RBI monthly) end months before fund prices, so the plain comparison is withheld ("periods do not line up"); this view ends the window where the shortest series ends, says so on every card, and runs each figure through the same engine agreement gate. An asset that cannot be checked over that window (too short, a gap, monthly data for volatility) is left out with its reason; fewer than two checked assets withholds the whole comparison. No model is involved. The strict plain comparison is unchanged (regression test).
- MEASURED: 267 tests pass in the sandbox (15 new), ruff and mypy clean; each chart line ends exactly where its verified total return says (test); panel checked in a headless browser (gold, silver, SBI Small Cap, 3 years to 1 Apr 2026: 149.28%, 224.89%, 42.78%). NOT yet checked in Chrome on the Windows machine.
- Limit: the shared period for anything including gold or silver currently ends 1 Apr 2026, so recent fund moves are not in that view.
