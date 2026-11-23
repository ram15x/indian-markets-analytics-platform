"""Three-way agreement run (A numpy, B DuckDB SQL, C Rust) over every series and window, including rolling returns,
gold, silver and USD/INR. Also checks that dates (start/end, drawdown peak/trough) agree, not only values."""
import sys, time, json, collections; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np
from imap.app import App
from imap.planners import RulePlanner
from imap import metrics_c
assert metrics_c.AVAILABLE, "build engine C first"
root = Path(__file__).parent.parent / "data"
eng = App(RulePlanner()).engine
stats = collections.Counter(); bad = []; t = time.time()
for code, s in eng.series.items():
    last = s.dates[-1]
    for label, yrs in (("1y", 1), ("3y", 3), ("5y", 5), ("inception", None)):
        start = str(last - np.timedelta64(365 * yrs, "D")) if yrs else str(s.dates[0])
        if yrs and np.datetime64(start) < s.dates[0]: continue
        jobs = [("total_return", {}), ("cagr", {}), ("max_drawdown", {}), ("volatility", {}), ("sip_xirr", dict(amount=5000, day=5))]
        if yrs: jobs.append(("rolling_return", dict(years=yrs, start=str(s.dates[0]))))
        jobs += [("sharpe", {}), ("sortino", {})]
        for m, kw in jobs:
            if m in ("sharpe", "sortino"):          # same window rule the app uses: ends at the last published T-bill week
                from imap.execute import _window, RF_COVER_DAYS
                st, en = _window(s, yrs if yrs else "inception", eng.rf[0][-1] + np.timedelta64(RF_COVER_DAYS, "D"))
                if yrs and np.datetime64(st) < s.dates[0]: continue
                kw = dict(start=st, end=en)
            else:
                kw = dict(dict(start=start, end=str(last)), **kw)
            r = eng.compute(m, code, **kw)
            if r.status == "VERIFIED":
                stats["VERIFIED_" + r.detail["engines"]] += 1
            elif r.reason.startswith("cannot"): stats["WITHHELD_all_agree_infeasible"] += 1
            elif "disagree" in r.reason: stats["WITHHELD_disagree"] += 1; bad.append((code, m, label, r.reason))
            else: stats["WITHHELD_rule"] += 1        # monthly series / FX gap rules
print(dict(stats), "in", round(time.time() - t, 1), "s")
for b in bad[:25]: print(b)
(root / "engine_agreement_abc.json").write_text(json.dumps(dict(engine_c=metrics_c.VERSION, stats=stats, disagreements=bad[:500]), indent=1, default=str))
