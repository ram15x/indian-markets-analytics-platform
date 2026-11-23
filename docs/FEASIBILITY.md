# Feasibility spike (2026-11-22)

Each line is marked MEASURED (I ran it), SOURCED (a document says so) or UNVERIFIED.
Nothing here is legal advice.

## Mutual funds: mfapi.in (third-party mirror of AMFI data)

- MEASURED: `GET /mf` lists 38,078 schemes. `GET /mf/{code}` returns metadata plus full NAV history.
  Example: SBI Small Cap Fund Direct Growth (125497): 3,211 rows, 18-11-2013 to 20-11-2026, ~127 KB,
  0.3 s, no non-positive NAVs, one 6-day gap.
- MEASURED: fields are `fund_house, scheme_type, scheme_category, scheme_code, scheme_name,
  isin_growth, isin_div_reinvestment`; dates are DD-MM-YYYY; NAV is a string with 5 decimals.
- MEASURED: rate limit. 80 quick requests returned HTTP 429 on 21. With a 0.7 s pause between
  requests, 60 of 60 succeeded and none were limited (46 s). The exact limit is UNVERIFIED.
  A first analysis that ignored this counted 429s as "empty schemes" and was discarded.
- MEASURED (sample of 80 random schemes): mean 816 rows per scheme, median 482, max 5,080.
  Extrapolated total about 31 million rows (rough; a sample).
- MEASURED: about 3 in 4 sampled schemes have no NAV in 2026 (matured or closed plans).
- MEASURED: metadata is sometimes scrambled (7 of 80 in one sample): `scheme_type` holding an ISIN
  string or a fund-house name. Matches the known AMFI-export errors listed by captn3m0/historical-mf-data
  (invalid ISINs, NAV values such as "#N/A", "N.A."). Loader must validate and quarantine.
- MEASURED (60 Direct+Growth schemes, paced): 21 of 60 active in 2026, mean 1,435 rows. Of 5,170
  Direct+Growth names, estimate about 1,800 active (a sample: wide interval, roughly 1,000 to 2,600).
- SOURCED: AMFI's own history download is limited to 90 days per request. mfapi.in is not an
  AMFI-operated API. UNVERIFIED: mfapi.in terms of use; AMFI terms for public redistribution.

## Storage against Neon free (1 GB)  [estimates, not measurements]

| Scope | Rows (est.) | Size (est., ~55 B/row with index) | Fits |
|---|---|---|---|
| All 38,078 schemes | ~31 M | ~1.7 GB | No |
| Active schemes, all plans | ~13 to 18 M | ~0.7 to 1.0 GB | Borderline |
| Active Direct+Growth (~1,800) | ~2.6 M | ~0.15 GB | Yes |
| NSE 500 stocks, 10 years daily | ~1.25 M | ~0.07 GB | Yes |
| Gold, silver, USD/INR daily | tiny | negligible | Yes |

Recommendation: v1 = active Direct+Growth funds. "All schemes" does not fit the free tier.

## Stocks: NSE

- SOURCED: NSE's research data list puts daily bhavcopy archives, historical index data (via
  niftyindices.com) and corporate actions in a freely available basket, but frames it as
  "non-commercial academic research" and says nothing about display on a website or app.
- SOURCED: NSE's data usage policy says ownership of data stays with NSE; users may not
  redistribute except as their agreement allows (clause 8.3); non-commercial users go through an
  approval route and reduced fees are discretionary (9.3, 10).
- SOURCED: NSE publishes an end-of-day data tariff with a line for display on a website or
  application (capital market and F&O segments listed at 1,10,000 INR domestic; the period is not
  stated in the text I could read).
- SOURCED: yfinance describes Yahoo's API as intended for personal use only.
- CONCLUSION: a public site must NOT display NSE or Yahoo prices without a licence. Stock questions
  stay local (personal use). UNVERIFIED whether derived figures (returns) count as derived data.
- Nifty 500 constituent list: SOURCED, downloadable as CSV from NSE's Nifty 500 page.

## Gold, silver and FX

- SOURCED: RBI's Handbook of Statistics publishes monthly average gold and silver prices in Mumbai
  (sourced from IBJA and others) and London/New York, free.
- SOURCED: LBMA moved its historic price tables behind a members' portal (Nov 2025), and
  gold.org removed historical LBMA data at the benchmark administrator's request. International
  daily gold history is licence-restricted.
- UNVERIFIED: any free, legal DAILY INR gold/silver series. IBJA's own site was not found; a data
  vendor lists IBJA series behind a login.
- SOURCED: RBI reference rate archive (USD/INR daily, Excel download). MSEI republishes it with a
  "for viewing only" disclaimer. UNVERIFIED: terms for reuse.
- Idea, UNVERIFIED: gold and silver exposure via fund NAVs already in the AMFI data.

## Corporate actions (splits, bonus)

- SOURCED: bhavcopy prices are not adjusted. Adjustment must be computed from corporate actions.
- SOURCED: corporate actions are in NSE's free research basket; an unofficial Python package
  (india-corp-actions) wraps NSE/BSE endpoints (cookie-based; terms unclear).
- UNVERIFIED: a clean free historical split/bonus source for all NSE 500 names.
- Rule: no stock return is shown unless prices are adjusted and the adjustment is verified on
  known cases (e.g. a documented split).

## Verdict

- Funds: feasible. Use active Direct+Growth; pace requests; validate and quarantine bad rows.
- Stocks: feasible locally; NOT cleared for a public site.
- Gold/silver: monthly RBI series is solid; a daily series is an open problem.
- Next: decisions in chat, then phase 2 (warehouse and metrics).

## Addendum: measured on the full archive (same day)

Source: captn3m0/historical-mf-data release v2026.11.22 (`funds.db.zst`, 381,792,073 bytes, MIT
licence on the scripts; the NAV data itself comes from AMFI). Table is `nav` (the README calls it
`funds`). All numbers below are MEASURED unless marked.

- 37,354,767 NAV rows, 37,795 schemes with NAVs, 2006-04-01 to 2026-11-22. 38,421 names in `schemes`.
- Active (last NAV in Nov 2026): 8,743 schemes, 17,878,850 rows (~1 GB: does not fit Neon free).
- Direct+Growth by name: 5,150 with NAVs; active: 1,799 schemes, 3,061,930 rows, mean 1,702 rows.
  Sample-based estimates earlier were close (1,800 schemes, 2.6 M rows).
- Data quality, active Direct+Growth: 0 duplicate (scheme, date) rows; 0 non-positive NAVs.
  558 daily moves over 10%, 54 over 20%, 23 over 50%, across 45 schemes. Example: scheme 119164,
  -98.9997% on 2022-11-27 (about a 100:1 unit change, not a real loss); scheme 120304, -89.9983%
  on 2026-06-20. Naive returns across such a date are wrong, so detection plus adjustment is required.
- 9 gaps over 10 days in 7 schemes; 2 gaps over 30 days.
- 7,159 rows sit inside a run of 5+ identical NAVs (stale or flat funds): needs a review rule.
- Dates fall on weekends too (Sat 29,627 rows, Sun 44,930), so "trading day" cannot be assumed.
