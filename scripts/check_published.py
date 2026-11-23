"""Compare engine output with figures printed in an AMC document (not used to tune anything).
Source: https://files.hdfcfund.com/s3fs-public/inline-files/ROSHI_JAIN-RP_15.pdf  (Oct 31, 2025, Regular Growth)
ELSS figures confirmed against a search excerpt of the same PDF; Focused/Flexi figures come from one
automated read of the PDF and are not independently confirmed."""
import sys, sqlite3; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from imap import dq
from imap.series import build_all
from imap.metrics_b import EngineB
from imap.engine import Engine

END = "2025-10-31"
PUB = {  # code: (name, published NAV, [(start, label, years, published return %)])
 101979: ("HDFC ELSS Tax Saver Reg Growth", 1457.899, [("2024-10-31","1y",1,8.68),("2022-10-31","3y",3,21.33),("2020-10-30","5y",5,25.98),("2015-10-30","10y",10,14.44)]),
 102760: ("HDFC Focused Fund Reg Growth", 238.421, [("2024-10-31","1y",1,9.77),("2022-10-31","3y",3,21.66),("2020-10-30","5y",5,29.22),("2015-10-30","10y",10,14.90)]),
 101762: ("HDFC Flexi Cap Reg Growth", 2068.833, [("2024-10-31","1y",1,10.20),("2022-10-31","3y",3,22.10),("2020-10-30","5y",5,29.36),("2015-10-30","10y",10,16.44)]),
}
con = sqlite3.connect("file:/tmp/mfdata/funds.db?mode=ro", uri=True)
nav = pd.read_sql(f"select scheme_code, date, nav from nav where scheme_code in ({','.join(map(str, PUB))})", con)
nav["date"] = pd.to_datetime(nav["date"]); nav = nav.drop_duplicates(["scheme_code","date"]).sort_values(["scheme_code","date"]).reset_index(drop=True)
ev, ad = dq.run(nav); print("DQ events on these 3:", ev[~ev.kind.isin(['STALE_RUN','GAP'])].kind.value_counts().to_dict() if len(ev) else {}, "adjustments:", len(ad))
series = build_all(nav, ev, ad); eng = Engine(series, EngineB(nav, ev, ad))
rows = []
for code, (name, pnav, pts) in PUB.items():
    s = series[code]; i = np.searchsorted(s.dates, np.datetime64(END), side="right") - 1
    print(f"{name}: archive NAV on {s.dates[i]} = {s.nav[i]} vs published {pnav}")
    for start, lab, yrs, pr in pts:
        r = eng.compute("cagr", code, start=start, end=END)
        days = r.detail["days"] if r.status == "VERIFIED" else None
        v = r.value * 100 if r.status == "VERIFIED" else np.nan
        ratio = r.detail["end_nav"] / r.detail["start_nav"] if r.status == "VERIFIED" else np.nan
        alt = (ratio ** (1 / yrs) - 1) * 100            # whole-years convention, for information only
        rows.append(dict(scheme=name, period=lab, start_used=r.detail.get("start_date"), published=pr, ours=round(v, 2), diff=round(v - pr, 2),
                         alt_years=round(alt, 2), alt_diff=round(alt - pr, 2), status=r.status))
R = pd.DataFrame(rows); pd.set_option("display.width", 200); print(R.to_string(index=False))
print("exact match at 2dp (ours):", int((R['diff'].abs() < 0.005).sum()), "/", len(R), "| within 0.05:", int((R['diff'].abs() <= 0.05).sum()), "| within 0.10:", int((R['diff'].abs() <= 0.10).sum()))
print("exact match at 2dp (alt years):", int((R['alt_diff'].abs() < 0.005).sum()), "/", len(R))
R.to_csv(Path(__file__).parent.parent / "data" / "published_check_hdfc.csv", index=False)
