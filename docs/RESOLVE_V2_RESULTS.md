# Fund-name resolution v2: results (2026-11-23)

Plan: docs/RESOLVE_EVAL.md (v2 section, two amendments made on dev evidence before the locked run).
Policy: RESOLVE only when one scheme matches by words, the query names its AMC, and (unless the query
is the full name) it uses >= 75% of the scheme's name words. Otherwise CLARIFY. Character similarity
only ranks candidates. Former names come from the scheme name text and data/renames.csv (10 sourced).

## Locked set (400 generated queries, scored once) vs bars
| Measure | Bar | Dev | Locked |
|---|---|---|---|
| RESOLVED to a wrong scheme | 0 | 0 | 0 |
| Coverage, AMC present: plain / known alias | >= 90% | 100% / 100% | 100% (177) / 100% (18) |
| Coverage, AMC present: typo | >= 80% | 100% (after Amendment 2) | 100% (101) |
| AMC absent: RESOLVED | 0 | 0 of 30 | 0 of 31 |
| AMC absent: true scheme in top 5 (<= 5 matches) | >= 90% | 100% (18) | 100% (21) |
| Ambiguous queries RESOLVED | 0 | 0 of 38 | 0 of 37 |
| Rename set: correct or CLARIFY with true in top 5 | >= 90% | 31 of 31 | 29 of 29 |
| Regression: five v1 failures not resolved to the wrong fund | all pass | 4 of 5 | **4 of 5** |
"Short" queries with the AMC present resolve only 45-51% of the time by design (they usually use less
than 75% of the name, so they get a CLARIFY list). No bar was set for them.

## Regression detail
- axis bluechip -> Axis Large Cap (correct per the AMC notice in renames.csv)
- hdfc top 100 -> HDFC Large Cap (correct per the AMC notice)
- icici pru bluechip -> ICICI Prudential Large Cap (erstwhile Bluechip) (correct per the name text)
- kotak emerging equity -> CLARIFY (v1 resolved wrongly). Intended fund unknown.
- **hdfc nifty 50 index -> RESOLVED to HDFC Nifty Next 50 Index. FAILED.** 4 of 5 query words match and
  the scheme has one extra word ("next"). No principled rule separates this from a correct match, so it
  is left failing and recorded here. Intended fund unknown.

## What this does not show
- The rename test is not held out: former names and data/renames.csv feed the resolver and also build the
  rename queries. It shows the mechanism works. It says nothing about renames that are not in the lists.
  Real renames not in the 10 + 27 will still fail (CLARIFY with the wrong candidates, or none).
- Queries are generated from scheme names. Nicknames, spoken shorthand and real user typos are not tested.
- One regression failure remains. v2 must still show the matched name and code and ask for confirmation.
- Scope is the 1,772 Direct+Growth schemes only; Regular plans and IDCW options are not indexed.
