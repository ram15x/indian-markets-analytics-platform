# Data-quality layer: pre-registered evaluation

Written 2026-11-22 BEFORE the detector code. Observed on real data first (dev evidence only):
face-value jumps of ~x100 / x10 (ratio = k * one day's growth, not exactly k), one-day glitches that
revert, a 14-day shift that later recovers (PGIM 138358, truth unknown), real crashes (silver FoFs
2026-01-30 and 2026-02-02, not to be adjusted), and persistent large jumps with no clean ratio
(ICICI Pru 120700 in 2015, probably a merger).

## Event classes
- SCALE_CHANGE: single-day ratio within 6% of k (see Amendment 2) or 1/k, k in {2,5,10,20,25,50,100,1000}, level stable
  on both sides. Adjusted: earlier NAVs multiplied by the clean k (so the real one-day return survives).
- BAD_VALUE: |daily move| > 10% and the next NAV is back within 3% of the prior one. Row excluded.
- TRANSIENT_SHIFT: |move| > 10%, back within 3% of prior level within 2..30 days. Flag only, never
  adjusted or excluded (cannot tell error from real).
- LARGE_MOVE: |move| > 10%, persistent, ratio not clean. Flag only, never adjusted.
- Info flags: STALE_RUN (>=5 identical NAVs), GAP (>10 days), WEEKEND_DATE.

## Amendment 1 (2026-11-22, before any scoring)
First run flagged 377 TRANSIENT_SHIFT events, because ordinary volatile weeks (COVID, silver) return
to the prior level within 30 days. TRANSIENT_SHIFT now additionally requires the return to happen in
one jump of >10% with the opposite sign. Gradual recoveries fall through to LARGE_MOVE, which also
holds real market moves; it is informational and never adjusts anything.

## Amendment 2 (2026-11-22, after first dev scoring; bars unchanged)
Dev scoring showed scale recall 0.956 and transient recall 0.845. Causes found on dev only:
(a) K_TOL 1.5% is too tight when an equity fund also moves 2-7% that day; raised to 6% (the clean
ratios are >=25% apart, so still unambiguous); (b) long excursions (12-29 days) drift more than 3%
from the prior level, so the return is now tested as r[t]*r[t+j] within 4% of 1 instead.

## Test
Inject known events into schemes that have no real move over 10%, split by scheme_code parity:
dev = even, locked = odd. Thresholds above were fixed from the dev evidence in this file; only dev may
be used to fix bugs. The locked set is scored once.
- 300 schemes per set. Per scheme one event type, drawn uniformly: scale change (random k, up or
  down), bad value (factor in [1.3,3] or [0.33,0.77]), transient shift (factor 0.6-0.85, 3-30 days),
  persistent real-like move (15-45% or 55-90% ratio, not within 3% of any clean k), and no event.
- Also scored: the real known cases 119164 (2014 up, 2022 down), 120304 (2026-06-20), 145536
  (2022-08-17), the quant spikes, and the silver FoFs (must not be adjusted).

## Bars (set before running)
- SCALE_CHANGE: recall >= 0.99, precision >= 0.99, recovered k exact.
- BAD_VALUE: recall >= 0.95.
- Persistent real-like moves: adjusted in 0% of cases (zero over-corrections).
- No-event schemes: zero adjustments.
- After adjustment, injected scale-change series must match the clean series to 1e-6 relative.
If a bar is missed we report it and narrow scope, not the bar.

## Known limit
A real persistent move within 1.5% of a clean ratio (e.g. exactly halving) is indistinguishable from
a unit change and will be adjusted. Rare, and listed here instead of hidden.
