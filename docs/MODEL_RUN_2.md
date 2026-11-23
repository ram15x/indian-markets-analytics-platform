# Second real-model run: planner v2, openai/gpt-oss-120b on Groq (2026-11-23, Ram's key)

File: data/planner_v2_eval_chat_openai_gpt-oss-120b.json. Rules and bars fixed in docs/PLANNER_EVAL_V2.md.

## Planner v2: PASSED the pre-registered bars
CORRECT 29 / WRONG_ANSWER 0 / SAFE_MISS 1 (bars: wrong <= 1, correct >= 25).
- The one miss: "liquid fund 1 year return" -> the model returned an empty plan with no notice; the validator
  rejected it (safe). The expected behaviour was CLARIFY.
- Code guards rejected no other plan, so the model's plans passed the year/SIP checks on their own.

### Read this before quoting the pass
- 30 questions by one author. The system prompt was rewritten after run 1 around the same categories the
  test checks (vague measure words, advice, prediction), so the prompt and test share a designer.
- Behaviours that scored CORRECT under the written rules but are not ideal (found by reading the plans):
  "Should I put my money in Mirae Asset Large Cap?" and "Is quant small cap a good buy...?" produced a notice
  and a fund lookup but no figures; the answer screen showed an empty "Matched: ." line. Fixed in the
  renderer after the run (outcome now NOTICE_ONLY); scores unchanged.
  "Which small cap fund will give the best returns?" produced the advice notice plus "which measure do you
  mean?", which invites a ranking question the system cannot answer without a named fund.
- One model, one run, temperature 0.

## Explainer v2: first attempt crashed (harness bug), not scored
scripts/eval_explainer_v2.py built its test funds through the resolver by full scheme name; names with a
former name in brackets (ICICI Prudential Value Fund (erstwhile Value Discovery Fund)) did not resolve, and
the script stopped at case 2. Nothing was saved. The harness now passes funds by scheme code (test only).
Case 1's paragraph was REJECTED for "the investment" (refers to particular funds). That text is generic, so
the rule is arguably too strict, but the checker is NOT changed after seeing output; the rerun uses the same
checker and the result will be reported as it comes.

## Explainer v2 rerun: FAILED (accepted 3 of 16; bar >= 13)
File: data/explain_v2_eval_openai_gpt-oss-120b.json. Same checker as pre-registered.
Rejection reasons: "the investment"/"your investment" x9, "both" x2 (as in "combining both price and
income"), "predictable" x2 (matched as a prediction word), "worst" x1 ("worst-case loss"), "percent" x1.
Most of these are false alarms: the words were used generically.

### More important: reading the texts shows the model's definitions are often wrong for our data
(my read; Ram to confirm). These would have passed a looser checker:
- Total return (4 texts): says it combines price change with "dividends"/"cash payouts received". Our funds
  are Growth options: nothing is paid out, and our total return is NAV change only. Misleading.
- SIP XIRR (2 rejected texts): "regardless of the exact dates" / "without worrying about the exact timing".
  Wrong: XIRR depends on the dates of each instalment.
- Volatility (1 rejected text): "look for the one with the lower volatility if you prefer smoother changes"
  is a selection suggestion (implied advice).
- Accepted text 1 (SIP XIRR): "It smooths out the ups and downs of the market" is mildly misleading;
  XIRR does not smooth anything, it is the single rate that fits the cash flows.
- Accepted texts 2 and 3 (CAGR): read as correct.
So the strict word checker blocked several wrong definitions by accident, and a word filter cannot check
meaning. Loosening it would let factual errors through.

## Decision proposed
Model-written definitions do not meet the bar and can be factually wrong about this data. Proposal: answers
use the developer-written glossary only (fixed text, reviewed once, versioned); the user's model is used for
planning, where code checks every output. Any future model-written explanation needs a meaning check
(e.g. against approved statements), not a word filter.

## Decision taken (2026-11-23, agreed with Ram)
Glossary only. Definitions live in data/glossary.json (versioned, editable without code). The model-written
explainer code is kept as src/imap/explain_experimental.py, unused by the app. The glossary text itself has
not been reviewed by anyone but its author yet.
