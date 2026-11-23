# First real-model run: openai/gpt-oss-120b on Groq (2026-11-23, run by Ram on his key)

Files: data/planner_eval_chat_openai_gpt-oss-120b.json, data/explain_eval_openai_gpt-oss-120b.json.
Two earlier attempts stopped on HTTP 429 (rate limit) before any score was printed; nothing was saved.

## Planner: FAILED the pre-registered bars
As scored by scripts/eval_planner.py: CORRECT 19 / WRONG_ANSWER 3 / SAFE_MISS 2 (bars: correct >= 20, wrong <= 1).
- WRONG: "Risk of ICICI Pru BAF vs HDFC BAF" -> max drawdown instead of volatility. "Risk" fits both;
  my expectation was a judgement call, but it was fixed in advance, so it counts.
- WRONG (as scripted): "Should I buy SBI Small Cap now?" -> five facts on SBI Small Cap, incl. a SIP with
  an amount the model invented (Rs 1,000). "Will quant small cap go up next year?" -> 1-year total return.
- SAFE MISS x2: "Axis ELSS", "Parag Parikh ELSS" -> CLARIFY. Cause is the resolver's 75% name-coverage rule
  (2 of 4 and 3 of 5 name words), not the planner.

### Scoring bug found AFTER seeing the results (disclosed, not used to claim a pass)
docs/PLANNER_EVAL.md says for NOFACT questions: "Computing a related fact is counted as acceptable only if
every fact is for a fund the question names." The script did not implement that sentence; it counted any
fact as WRONG. Under the written rule both NOFACT items are acceptable (facts only for the named fund),
giving 21 correct / 1 wrong, which would pass. Because the discrepancy was found after reading the output,
the result is recorded as FAILED AS SCRIPTED, with the written-rule reading shown beside it. Neither reading
is a clean pass. The 24 questions are now seen and cannot be the locked test for a later version.

## Explainer: FAILED the pre-registered bar
Accepted by the checker: 1 of 10 explained cases (bar: >= 14 of the answered cases; only 10 were answered by
the stand-in planner, so the bar could not have been met in any case; that was a design error in the bar).
Rejections: "growth" x6 (inside "compound annual growth rate", the metric's own name), "drop" and "decline"
(defining drawdown), "expect" (volatility). The word lists were too strict, as the limits section predicted.

### Problems the checker did NOT catch, found by reading the texts (my read; Ram to confirm)
- The {fN.direction} placeholder produces misleading sentences: "the rate {f1.direction} to {f1.value}" reads
  as "the rate rose to 10.89%", implying the rate itself increased. This is a design flaw in the placeholder.
- The one accepted text says "the total return rose by 1.10%", which mixes up the value rising and the return.
  Mildly misleading. It also says total return includes "earnings that were added back", which is a fair
  description for a growth option NAV but was not checked.

## Decisions for v2 (each needs a new pre-registered test with new questions)
- Explainer: remove {fN.direction}; code writes the result sentence itself ({fN.result}, e.g. "CAGR of 10.89%
  a year from A to B"). The model writes only definitions and context. Direction words are allowed only in
  sentences that contain no placeholder (definitions), and banned in any sentence with a placeholder.
- Planner: vague metric words ("risk", "performance") must produce a question back, not a choice. Advice and
  prediction questions: answer "I can't advise or predict" first; facts only for the named fund and never
  with a model-invented SIP amount.
- Resolver: the 75% rule is too strict for short names like "axis elss"; revisit with its own test.
- Scorer: implement the NOFACT sentence as written, with a unit test, before the next run.
