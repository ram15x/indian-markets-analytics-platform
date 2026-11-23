"""Compare engine output with figures printed by the fund house itself (not used to tune anything).

Source: Nippon India Mutual Fund monthly product notes, "Scheme performance summary", DIRECT plan rows
  https://mf.nipponindiaim.com/FundsAndPerformance/ProductNotes/NipponIndia-Small-Cap-Fund-Sep-2026.pdf  (as on 30 Sep 2026)
  https://mf.nipponindiaim.com/FundsAndPerformance/ProductNotes/NipponIndia-Small-Cap-Fund-Aug-2026.pdf  (as on 31 Aug 2026)
  https://mf.nipponindiaim.com/FundsAndPerformance/ProductNotes/NipponIndia-SmallCap-Fund-Jul-2026.pdf   (as on 31 Jul 2026)
Each table gives the Direct NAV, the value of Rs 10,000 and the return % for 1, 3 and 5 years and since the Direct plan's
inception (1 Jan 2013). The figures were read by an automated fetch of each PDF; they agree with the same figures
quoted by a second site for 30 Sep 2026 (5paisa: 9.97 / 14.69 / 18.36).
Run from the project root with the real data built:  python scripts/check_published_nippon.py"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pandas as pd
from imap.app import App
from imap.planners import RulePlanner
from imap import metrics_a as A

PUB = {   # as-on date: (published NAV, {period: (value of Rs 10,000, return %)})
    "2026-09-30": (204.5942, {"1y": (10997, 9.97), "3y": (15097, 14.69), "5y": (23238, 18.36), "since inception": (187759, 23.77)}),
    "2026-08-31": (210.6609, {"1y": (11426, 14.17), "3y": (15747, 16.32), "5y": (24963, 20.07), "since inception": (193326, 24.19)}),
    "2026-07-31": (203.1573, {"1y": (10699, 6.99), "3y": (15915, 16.74), "5y": (24267, 19.38), "since inception": (186440, 24.03)}),
}
YEARS = {"1y": 1, "3y": 3, "5y": 5}
INCEPTION = "2013-01-01"

app = App(RulePlanner()); eng = app.engine
code = next(int(c) for c, n in zip(app.resolver.codes, app.resolver.names, strict=True) if n.lower().startswith("nippon india small cap fund") and "direct" in n.lower())
s = eng.series[code]
rows = []
for end, (pnav, periods) in PUB.items():
    i = A.asof(s, end)
    rows.append(dict(as_on=end, period="NAV on that day", published=pnav, ours=round(float(s.nav[i]), 4), diff=round(float(s.nav[i]) - pnav, 4), value_10k_ours=None, value_diff=None))
    for lab, (pval, pret) in periods.items():
        start = INCEPTION if lab == "since inception" else str((pd.Timestamp(end) - pd.DateOffset(years=YEARS[lab])).date())
        # The first run used total return for 1 year; one row (31 Aug 2026) then differed by 0.09. The fund house annualises with
        # actual days / 365 for every period of a year or more (the period 29 Aug 2025 to 31 Aug 2026 is 367 days), which is what
        # the engine's CAGR does, and what scripts/check_published.py (HDFC) already used. Recorded in docs/ENGINE_RESULTS.md.
        r = eng.compute("cagr", code, start=start, end=end)
        if r.status != "VERIFIED":
            # since inception: the archive's first NAV is dated after the plan's inception date, so the engine withholds.
            # For information only, also compute from the first NAV in the archive (not counted in the tallies).
            r2 = eng.compute("cagr", code, start=str(s.dates[0]), end=end)
            info = dict(first_nav_date=str(s.dates[0]), first_nav=float(s.nav[0]), cagr_from_first_nav=round(r2.value * 100, 2) if r2.status == "VERIFIED" else None)
            print(f"{end} since inception: engine says {r.status} ({r.reason}); information only: {info}, published {pret}")
            continue
        ratio = r.detail["end_nav"] / r.detail["start_nav"]
        ours = r.value * 100
        rows.append(dict(as_on=end, period=lab, start_used=r.detail["start_date"], published=pret, ours=round(ours, 2), diff=round(ours - pret, 2),
                         value_10k_ours=round(10000 * ratio), value_diff=round(10000 * ratio) - pval, status=r.status))
R = pd.DataFrame(rows); pd.set_option("display.width", 220); print(R.to_string(index=False))
p = R[R.period != "NAV on that day"]
print(f"\nreturns: exact at 2 decimals {int((p['diff'].abs() < 0.005).sum())}/{len(p)}; within 0.05: {int((p['diff'].abs() <= 0.05).sum())}/{len(p)}; "
      f"within 0.10: {int((p['diff'].abs() <= 0.10).sum())}/{len(p)}; value of Rs 10,000 within Rs 1: {int((p['value_diff'].abs() <= 1).sum())}/{len(p)}")
n = R[R.period == "NAV on that day"]; print(f"NAV on the day: exact to 4 decimals {int((n['diff'].abs() < 0.00005).sum())}/{len(n)}")
