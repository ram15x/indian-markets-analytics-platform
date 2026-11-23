# Planner eval v4: held-out check of the prompt fix

v3 failed (14/21, see `PLANNER_EVAL_V3.md`) and the prompt was changed in response. v4 has 17 **new** questions with different wording, written after the fix but with expected answers fixed before any model run. Do not edit them after a run.

Same scoring as v2/v3. Bars, set before running: WRONG_ANSWER <= 1 and CORRECT >= 14 of 17 (about 80%).

Contents: 11 answerable (gold, silver, USD/INR including volatility, which is allowed on the daily rate; Sharpe/Sortino on funds, including a comparison), 3 that must be withheld (Sharpe on silver, SIP in silver, Sortino on USD/INR), 3 with no figure (advice, prediction, definition).

Rule-based stand-in baseline: 12 CORRECT, 5 SAFE_MISS, 0 WRONG_ANSWER. The misses are limits of the regex stand-in, not of the system.

Run: `python scripts\eval_planner_v4.py chat openai/gpt-oss-120b` (key in `$env:GROQ_API_KEY`).

**Status: not yet run against a language model.**
