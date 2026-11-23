"""Second fund house check: Axis Small Cap Fund, DIRECT plan, as on 31 Aug 2026 (Axis product leaflet, read by automated fetch;
row labels were unlabeled in the extraction, so values were matched by size). Not used to tune anything.
Published: 1y 15.38% / Rs 11,547; 3y 16.65% / Rs 15,879; 5y 17.28% / Rs 22,200; since inception 22.84% / Rs 138,131 (allotment 29 Nov 2013 at Rs 10).
Run from the project root with real data built:  python scripts/check_published_axis.py"""
import sys; from datetime import date; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pandas as pd
from imap.app import App
from imap.planners import RulePlanner
app = App(RulePlanner()); eng = app.engine; code = 125354; end = "2026-08-31"
PUB = {1: (15.38, 11547), 3: (16.65, 15879), 5: (17.28, 22200)}
for y, (pr, pv) in PUB.items():
    st = str((pd.Timestamp(end) - pd.DateOffset(years=y)).date()); r = eng.compute("cagr", code, start=st, end=end)
    v = round(10000 * r.detail["end_nav"] / r.detail["start_nav"])
    print(f"{y}y {r.status} cagr {r.value*100:.2f} (pub {pr}, diff {r.value*100-pr:+.2f}) | Rs10,000 -> {v} (pub {pv}, diff {v-pv:+d})")
# since inception from the Rs 10 allotment price (the archive starts later, at 5 Dec 2013, NAV 10.01)
end_nav = 138.13; d = (date(2026, 8, 31) - date(2013, 11, 29)).days
print(f"since inception from Rs 10 on 29 Nov 2013: {((end_nav/10)**(365/d)-1)*100:.2f}% (pub 22.84), Rs {round(10000*end_nav/10)} (pub 138131; 1 rupee from NAV rounding)")
