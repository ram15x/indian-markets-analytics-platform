# Fund-name resolution: pre-registered evaluation

Written 2026-11-22 BEFORE the resolver code. Universe: the 1,772 Direct+Growth schemes in
data/schemes.parquet. Names there look like "Aditya Birla Sun Life Short Term Fund - Growth - Direct Plan".

## Behaviour being tested
Given a query, the resolver returns either RESOLVED(one scheme code) or CLARIFY(up to 5 candidates).
The costly error is RESOLVED to the wrong scheme. Asking when it could have answered is the cheaper error.

## Query generator (truth is known from the source scheme)
Core tokens = lowercase name tokens, minus parenthetical text and the words fund, plan, option, direct,
growth, scheme. Each sampled scheme gets one query type, uniformly:
- plain: core tokens in order.
- alias: AMC words replaced with a short form. Two sets: KNOWN aliases (in the resolver's dictionary:
  "icici prudential"->"icici pru", "aditya birla sun life"->"absl", "nippon india"->"nippon") and
  UNSEEN aliases (not in the dictionary: "kotak mahindra"->"kotak", "sbi mutual"->"sbi", "hdfc mutual"->"hdfc"
  where the long form is prepended to the source name's AMC). Reported separately.
- typo: plain plus one edit (substitution, deletion or swap) in one word of length >= 5.
- short: a random subset of core tokens (size max(2, ceil(0.6 n)), order kept).
Truth class from the CLEAN token set (before alias/typo): the set of schemes whose core tokens contain
all query tokens. Size 1 = UNIQUE (must resolve to that scheme). Size >= 2 = AMBIGUOUS (must not
confidently pick one; should CLARIFY with the source scheme among the candidates when the set is <= 5).

## Split
dev = source schemes with even scheme_code, locked = odd. 400 queries each (seeds 1122 / 1123). Thresholds
and the alias dictionary may be changed using dev only. Locked is scored once; a second run is refused.

## Bars (set before running)
- Confident-wrong: RESOLVED to a wrong scheme on UNIQUE queries <= 1.0%.
- Over-confident on AMBIGUOUS queries (RESOLVED when truth set >= 2) <= 10%.
- Coverage on UNIQUE queries (RESOLVED correct): plain/known-alias >= 85%, typo >= 75%, unseen alias reported only.
- When CLARIFY on a UNIQUE query, the true scheme is in the 5 candidates >= 95%.

## Amendment 1 (2026-11-23, after first dev scoring, before locked)
Dev run 1: confident-wrong 0%, but over-confident on ambiguous 70.7% (bar 10%) and true-in-top-5 after
CLARIFY 75% (bar 95%). Findings: (a) 30 of 82 "ambiguous" dev cases were plain queries equal to the
source's full core name that also happen to be contained in a longer name elsewhere. A query that
equals exactly one scheme's full core token set is now expected to RESOLVE to it; the ambiguous class
excludes those. The bar of 10% applies to the rest. (b) typos in short distinctive words break
character n-gram matching, so the resolver now spell-corrects query words against the name vocabulary
and, when several schemes contain every query word, returns CLARIFY. The resolver now implements the
same containment idea the truth uses, so on clean queries ambiguity handling is partly by construction;
typo and alias queries are where it is really tested.

## Starting method (lexical only)
Normalise, expand known aliases, character 3-5-gram TF-IDF cosine against normalised names.
RESOLVED if top score >= 0.50 and (top1 - top2) >= 0.05, else CLARIFY. Embeddings are added only if
lexical misses a bar on dev AND an embedding model can actually be obtained here; otherwise we report
the miss.

## Limits stated now
Queries are generated from the names themselves, so real user phrasing (e.g. "the sbi small cap one",
fund nicknames, misspelt AMCs) is not represented. Scores here do not predict real-world accuracy.
A small hand-written set is shown for demonstration only, unscored, single annotator.

---
# v2 (2026-11-23): pre-registered BEFORE the v2 code

Motivation: docs/RESOLVE_RESULTS.md (v1 confidently resolved old names to the wrong fund).
New split (v1's locked set is spent): scheme_code % 3 == 0 -> dev, == 1 -> locked, == 2 unused.
Seeds: dev 2301, locked 2302. 400 generated queries each, same five types as v1.

## v2 policy
RESOLVE only when (a) a single scheme matches by word containment or full name, AND (b) the query
contains that scheme's leading word (the AMC word, e.g. sbi, hdfc, icici) or the leading word of a
former name. Otherwise CLARIFY. Character similarity only ranks candidates; it never resolves.
Former names are matched too: (formerly known as X) and (erstwhile X) text inside scheme names, plus
data/renames.csv (10 renames, each with a source URL; target scheme found by its current name).

## Expected outcome per query
- AMC word present and exactly one scheme matches (or the query is a scheme's full name): RESOLVED to it.
- AMC word absent, or several schemes match: CLARIFY, true scheme in the 5 candidates when <= 5 match.

## Rename set (small, reported as counts, no statistical claims)
Items: 27 schemes with a former name in the archive, plus the 10 sourced renames. Split by position in
code order (even = dev, odd = locked). Query = the old name as written; for in-archive former names also
a variant with the current leading word prepended. Pass = never RESOLVED to a wrong scheme.

## Regression set (the five v1 failures)
"axis bluechip", "hdfc top 100", "icici pru bluechip", "kotak emerging equity", "hdfc nifty 50 index".
Pass = none RESOLVED to the scheme v1 wrongly picked. (Intended targets are known only for the first
three, from sources; the last two have no known target and only must avoid the wrong pick.)

## Bars
- RESOLVED to a wrong scheme: 0 on the locked generated set, 0 on the rename set, 0 on the regression set.
- AMC-present unique queries: coverage plain/known-alias >= 90%, typo >= 80%.
- AMC-absent queries: RESOLVED rate 0%; true scheme in top 5 >= 90% when <= 5 schemes match.
- Rename set: RESOLVED correct, or CLARIFY with the true scheme in the top 5, for >= 90% of items.

## Stated limits
Rename coverage is 10 sourced + 27 in-archive items out of an unknown number of real renames. Any rename
not in these lists will still fail to resolve (it will CLARIFY or return wrong candidates). The queries
are still generated from names, not collected from people.

## v2 Amendment 1 (2026-11-23, after hand-checking ten queries, BEFORE the first v2 dev scoring)
(a) A former name's first word is not treated as an AMC word ("bluechip" is not an AMC); only the current
leading word counts. (b) A non-exact single match must also cover >= 75% of the scheme's name words
(otherwise "kotak emerging equity" resolved to a Kotak global emerging-market FoF with 8 name words).
Residual risk stays: a query that is one extra word short of a different fund ("hdfc nifty 50 index" vs
"HDFC Nifty Next 50 Index", 80% covered) still resolves to it. Showing the matched name for confirmation
remains mandatory.

## v2 Amendment 2 (2026-11-23, after first v2 dev scoring)
Dev: 0 resolved-wrong, rename ok 100%, AMC-absent resolved 0, but typo coverage 77.2% (bar 80%) and the
regression query "hdfc nifty 50 index" still resolved to HDFC Nifty Next 50 (bar: must not). Typo misses
were all adjacent-letter swaps, which plain edit distance counts as two edits; switched to Damerau
distance (swap = 1). The regression failure is NOT fixed: no principled rule separates it from a correct
single-word-short match, so it is reported as a failed regression item.

---
# v3 (2026-11-23): pre-registered BEFORE the v3 code

Motivation: docs/MODEL_RUN_1.md: "axis elss" and "parag parikh elss" got CLARIFY because they use 2 of 4 and
3 of 5 name words, below the 75% rule.
Change (the only one): a single non-exact word match with the AMC named also RESOLVES when it leaves at
most 2 of the scheme's name words unused AND uses at least 50% of them. The 75% path stays.
Split: dev = scheme_code % 3 == 0 (seen before), locked = scheme_code % 3 == 2 (never used). Seeds 2401 / 2402.
Same generator and measures as v2, plus regression items:
- must RESOLVE correctly: "axis elss" -> 120503, "parag parikh elss" -> 147481, "axis bluechip" -> 120465,
  "hdfc top 100" -> 119018, "icici pru bluechip" -> 120586.
- must NOT resolve to v1's wrong pick: "kotak emerging equity".
- known failure kept: "hdfc nifty 50 index" (still expected to resolve to Nifty Next 50; reported).
Bars: same as v2 (0 wrong resolves on locked generated set and rename set; coverage plain/alias >= 90%,
typo >= 80%; AMC-absent resolved 0) plus all must-resolve regression items correct.
Expected trade-off, stated now: "short" queries will resolve more often, so the wrong-resolve count is the
number to watch.
## v3 Amendment 1 (dev only, before locked)
Dev had 1 wrong resolve: generated short query "tata mid cap" (from "Tata Large & Mid Cap") equals the full
name of another scheme, "Tata Mid Cap Fund", and resolved to it. As in v1 Amendment 1, a query equal to
exactly one scheme's full name now has that scheme as its truth. Not a resolver change.
