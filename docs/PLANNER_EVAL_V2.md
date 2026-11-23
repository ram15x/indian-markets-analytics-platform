# Planner v2 and explainer v2: pre-registered evaluation

Written 2026-11-23 after the failed first run (docs/MODEL_RUN_1.md) and BEFORE any v2 code is run with a
model. Questions: data/planner_eval_v2.json (30 new questions, one author; every fund code and window was
checked against the data before writing this file). The v1 questions are not reused.

## Planner v2 behaviour
- Vague measure words ("risky", "performed", "risk") -> the plan contains an `ask` step; the user is asked
  which measure they mean. Outcome ASK.
- Advice or prediction questions -> the plan sets `notice` ("advice" or "prediction"). The answer starts by
  saying it cannot advise or predict. Facts are allowed only for funds the question names.
- Code guards on the plan, using the question text: a SIP amount must be written in the question, else the
  plan must leave it out (code then uses Rs 5,000 and says so; XIRR does not depend on a constant amount);
  a SIP day other than 1 must be written in the question; a stated number of years must match the plan;
  with no years stated, the plan must use 3 or, if the question says inception/since start, "inception".

## Outcomes and scoring
Expected types: ANSWER (exact fact set and compare flag), ASK, CLARIFY, WITHHELD, NOTICE (named funds
listed), NOFACT (no facts at all).
- CORRECT: ANSWER with exactly the expected facts; ASK/CLARIFY/WITHHELD as expected; NOTICE outcome
  carries the notice and every fact (if any) is for a listed fund; NOFACT yields no facts.
- WRONG_ANSWER: facts that differ from the expected set; any fact where ASK, CLARIFY, WITHHELD or NOFACT
  was expected; for NOTICE, a fact without the notice or for an unlisted fund.
- SAFE_MISS: everything else (asked or refused when an answer was expected).
The scorer has unit tests for each rule (tests/test_scoring.py) written before the run.

## Bars (one run per model, temperature 0)
- WRONG_ANSWER <= 1 of 30.
- CORRECT >= 25 of 30.

## Explainer v2
Code writes every result sentence (number, direction, dates, a Rs 10,000 illustration). The model writes
only a short paragraph explaining what the measures mean, with no reference to the specific funds.
Checker rejects: digits, %, Rs/INR, fund-house words, advice/prediction/judgement words, and references to
particular funds ("the fund", "this fund", "both funds", "first", "second", ...). If rejected, a fixed
glossary written by the developer is shown instead (labelled as such).
Test: the 16 ANSWER questions, built directly from their expected facts (so the planner does not limit the
count). Bars: accepted >= 13 of 16; human read of every accepted paragraph by Ram: 0 misleading
definitions, 0 implied advice or prediction.

## Limits
Thirty questions by one person. Guards remove some model errors by construction, so a pass shows the
whole system behaves on these questions, not that the model plans well on its own.
