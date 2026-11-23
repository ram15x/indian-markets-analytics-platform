"""Weak outside check of volatility and Sharpe. Published (PPFAS Parag Parikh Flexi Cap August 2026 factsheet, as relayed by taxguru.in/?p=1087130,
a secondary source): standard deviation 9.93%, Sharpe 0.80. The factsheet's window, return frequency and risk-free rate were NOT confirmed
(3 years to 31 Aug 2026 is assumed). Treat a match as consistency, not proof. Run from the project root with real data built."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from imap.app import App
from imap.planners import RulePlanner
e = App(RulePlanner()).engine; code, st, end = 122639, "2023-08-31", "2026-08-31"
for m, pub in (("volatility", 0.0993), ("sharpe", 0.80)):
    r = e.compute(m, code, start=st, end=end); print(f"{m}: ours {r.value:.4f} ({r.status}) published {pub}")
s = e.series[code]; d = pd.Series(s.nav, index=pd.to_datetime(s.dates)).resample("ME").last(); d = d[(d.index >= st) & (d.index <= end)]
print(f"monthly-return convention: {d.pct_change().dropna().std(ddof=1) * np.sqrt(12):.4f}")
