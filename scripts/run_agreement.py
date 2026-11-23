"""Run both implementations over every scheme and window; report disagreements."""
import sys, time, json; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from imap.series import build_all
from imap.metrics_b import EngineB
from imap.engine import Engine
root = Path(__file__).parent.parent / "data"
nav = pd.read_parquet(root / "nav_raw.parquet"); ev = pd.read_parquet(root / "dq_events.parquet"); ad = pd.read_parquet(root / "dq_adjustments.parquet")
t = time.time(); series = build_all(nav, ev, ad); eng = Engine(series, EngineB(nav, ev, ad)); print("setup", round(time.time() - t, 1), "s")
END = "2026-11-20"; stats = {"VERIFIED": 0, "WITHHELD_agree_infeasible": 0, "WITHHELD_disagree": 0}; bad = []; per = {}
t = time.time()
for code, s in series.items():
    last = s.dates[-1]
    for label, yrs in (("1y", 1), ("3y", 3), ("5y", 5), ("inception", None)):
        start = str(last - np.timedelta64(365 * yrs, "D")) if yrs else str(s.dates[0])
        if yrs and np.datetime64(start) < s.dates[0]: continue
        for m, kw in (("total_return", {}), ("cagr", {}), ("max_drawdown", {}), ("volatility", {}),
                      ("sip_xirr", dict(amount=5000, day=5))):
            r = eng.compute(m, code, start=start, end=str(last), **kw)
            key = (m, label)
            if r.status == "VERIFIED": stats["VERIFIED"] += 1
            elif r.reason.startswith("cannot"): stats["WITHHELD_agree_infeasible"] += 1
            else: stats["WITHHELD_disagree"] += 1; bad.append((code, m, label, r.reason))
print(stats, "in", round(time.time() - t, 1), "s")
for b in bad[:20]: print(b)
(root / "engine_agreement.json").write_text(json.dumps(dict(stats=stats, disagreements=bad[:200]), indent=1, default=str))
