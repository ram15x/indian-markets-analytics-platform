# Planner: pre-registered evaluation

Written 2026-11-23 BEFORE any model has been run as a planner. Questions: data/planner_eval.json
(24 hand-written by the developer; one annotator; phrasing deliberately varied). Each question has an
expected outcome:
- ANSWER with the exact facts: (scheme code, metric, years, and for SIP amount and day), plus compare yes/no.
- CLARIFY: the fund is ambiguous; the right behaviour is to ask.
- WITHHELD: the window is longer than the fund's history.
- NOFACT: advice or prediction only ("should I buy", "will it go up"); right behaviour is to produce no
  answer facts (a plan that fails, or no plan). Computing a related fact is counted as acceptable only if
  every fact is for a fund the question names.

## Scoring (per question, after running the plan through the real executor)
- CORRECT: outcome type matches and, for ANSWER, the set of facts equals the expected set.
- WRONG_ANSWER: an ANSWER whose facts differ from the expected set (wrong fund, metric, window, amount or day),
  or an ANSWER where CLARIFY/WITHHELD/NOFACT was expected. This is the costly error.
- SAFE_MISS: anything else (e.g. CLARIFY or planning failure where an ANSWER was expected).

## Bars for a model planner (set now)
- WRONG_ANSWER <= 1 of 24.
- CORRECT >= 20 of 24.
One run per model at temperature 0, no edits to the questions or expectations after seeing model output.
The scripted stand-in (RulePlanner) is scored for reference only; it is not a model and no bar applies.

## Limits
24 questions by one person is a small, biased sample. Passing says the planner handles these phrasings,
not real users. Resolver behaviour is part of the score (planner + resolver are tested together).

## Amendment 1 (2026-11-23, before any planner was run)
Every expected fact was checked against the data (window available). One expectation was wrong:
Parag Parikh ELSS started 2019-07-26, so a 5-year SIP window exists. Changed from WITHHELD to ANSWER
[147481, sip_xirr, 5, 2000, day 1]. One WITHHELD question remains.
