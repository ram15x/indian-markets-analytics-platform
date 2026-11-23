# Planner eval v3: gold, silver, USD/INR, Sharpe and Sortino

The locked v2 set (30 questions) was written before these features existed, so it does not cover them. This set (21 questions) does.
Expected answers were written from the rules, **before any language model saw the questions**. Do not edit them after a run.

Scoring is the same as v2 (`src/imap/scoring.py`): CORRECT, SAFE_MISS (the system declined or asked, no wrong figure), WRONG_ANSWER (a wrong or unexpected figure).
Bars, set before running: WRONG_ANSWER <= 1 and CORRECT >= 17 of 21 (the same 80% as v2).

| Group | Questions | What it tests |
|---|---|---|
| Ratios on funds | 3 | Sharpe/Sortino map to the right metric, fund and years |
| Gold, silver, USD/INR | 7 | Macro codes (-1, -2, -3), not a fund; "dollar vs rupee" wording |
| Name traps | 2 | "SBI Gold Fund" must go to the fund, not to gold |
| Must be withheld | 5 | Sharpe on gold or USD/INR, volatility and SIP on monthly series, gold vs a fund (periods differ) |
| No figure at all | 5 | Predictions, advice, definitions |

Rule-based stand-in baseline (no model): 19 CORRECT, 2 SAFE_MISS, 0 WRONG_ANSWER. The two misses are USD/INR phrased as "dollar against the rupee".

Run (one run per model; the key stays in your environment, never in a file):

    $env:GROQ_API_KEY = "<your key>"
    python scripts\eval_planner_v3.py chat openai/gpt-oss-120b

Results are saved to `data/planner_v3_eval_<model>.json`.

## Result (openai/gpt-oss-120b, prompt before the fix): FAILED the bar
14 CORRECT, 0 WRONG_ANSWER, 7 SAFE_MISS (bar was 17 correct).
- 6 misses: the model returned a plan with no steps ("plan must have 1..12 steps") for silver alone, USD/INR (twice), gold drawdown, USD/INR Sortino and silver volatility.
- 1 miss: "SIP of 5000 a month in gold" was treated as a prediction, with no steps.
- Cause: the prompt only described mutual funds, so the model did not know gold, silver and the dollar are valid subjects. Gold CAGR and gold-vs-silver worked, probably by luck.
- Safety held: no wrong figure was given. Every failure was a safe refusal.

The prompt was then changed (it now names gold, silver and USD/INR and the Sharpe/Sortino words). **That makes this set no longer a clean test**, because the fix was written after seeing these questions. A rerun on it would flatter the result. The fix is judged on a new set, `PLANNER_EVAL_V4.md`.
