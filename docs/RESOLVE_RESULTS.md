# Fund-name resolution v1: results (2026-11-23)

Method: spell-correct query words against the name vocabulary, then (1) exact full-name match,
(2) the only scheme containing all words, (3) CLARIFY when several schemes contain all words,
(4) fallback to character n-gram similarity with a score and margin rule.
Plan: docs/RESOLVE_EVAL.md (pre-registered, one amendment made on dev evidence before the locked run).

## Pre-registered scores (generated queries, 400 per split)
| Measure | Bar | Dev | Locked |
|---|---|---|---|
| Confident-wrong on UNIQUE queries | <= 1% | 0% | 0% |
| Over-confident on AMBIGUOUS queries | <= 10% | 2.8% (1 of 36) | 0% (0 of 23) |
| Coverage plain / known alias | >= 85% | 100% / 100% | 100% / 100% |
| Coverage typo | >= 75% | 98.5% | 97.4% (74 of 76) |
| True scheme in 5 candidates after CLARIFY | >= 95% | 100% | 100% |
Unseen-alias coverage was 100% but is trivial: those queries keep the first word of the name.

## Why these scores overstate real-world accuracy
- Queries are generated from current scheme names, so they never contain nicknames, old names or
  mistakes a person makes that are not simple typos.
- On clean queries the resolver and the truth use the same word-containment idea, so ambiguity
  handling is partly by construction. Typo queries are the only real test of the spell correction.
- The 400 queries per split sample the same 1,772 names.

## Known failure found after the locked run (hand-written demo, unscored, one annotator)
The resolver confidently returned a different fund when the query used a name that has since changed
or that omitted words:
- "axis bluechip" -> ICICI Prudential US Bluechip Equity (character-match fallback)
- "icici pru bluechip" -> ICICI Prudential US Bluechip Equity ("only scheme containing all words")
- "hdfc top 100" -> HDFC Nifty 100 Index (fallback)
- "kotak emerging equity" -> a Kotak global emerging-market FoF
- "hdfc nifty 50 index" -> HDFC Nifty Next 50 Index
The intended funds for the first three appear to be renamed (Axis Large Cap, ICICI Prudential Large Cap
"erstwhile Bluechip", HDFC Large Cap); that reading is mine and is not confirmed by an AMC notice.
Causes in the code: (a) the tokenizer drops parenthetical former names, e.g. "(erstwhile Bluechip Fund)"
(27 schemes carry one); (b) renames that the archive does not record cannot be resolved at all;
(c) the character-match fallback ignores a mismatched AMC; (d) a unique word-containment match is
trusted even when the query is short.
Consequence: v1 must not be wired to answers without showing the matched scheme name and code and
asking for confirmation. v1 is not safe for old names.

## v2 plan (needs a NEW pre-registered test; the locked set above is spent)
1. Index former names from the name text as extra aliases (27 schemes; real ground truth).
2. Remove the fallback RESOLVE; character match may only rank CLARIFY candidates.
3. Require the AMC to match for a RESOLVE.
4. Source a rename list for renames the archive lacks (SEBI recategorisation, AMC notices) and label it
   SOURCED or UNVERIFIED per entry.
5. Add held-out rename queries to the generator and a fresh locked split.
