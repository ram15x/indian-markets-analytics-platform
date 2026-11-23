"""Post-hoc checks on experiment 1 (NOT part of the pre-registered rule; labelled as such in the write-up)."""
import numpy as np, pandas as pd, json
from pathlib import Path
root = Path(__file__).parent.parent; T = pd.read_parquet(root / "lab/results/vol_forecast_rows.parquet")
rng = np.random.default_rng(11); T["month"] = T.origin.dt.to_period("M")
out = {}
def block(a, b):
    d = T.groupby("month").apply(lambda g: (g["q_" + a] - g["q_" + b]).mean(), include_groups=False).to_numpy()   # one number per calendar month
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(5000)]
    return dict(mean_diff=float(d.mean()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], months=len(d), share_months_a_better=float((d < 0).mean()))
for a, b in (("garch", "har"), ("garch", "b3"), ("b3", "har"), ("lgbm", "har")): out[f"{a}_vs_{b}"] = block(a, b)
ex = T[T.yr != 2020]; out["excluding_2020_overall_qlike"] = {m: float(ex["q_" + m].mean()) for m in ("b1", "b2", "b3", "har", "garch", "lgbm")}
T["calm"] = T.rv63 < T.rv63.median(); out["qlike_by_regime"] = {r: {m: float(g["q_" + m].mean()) for m in ("b3", "har", "garch", "lgbm")} for r, g in zip(("calm_prior_vol", "stressed_prior_vol"), (T[T.calm], T[~T.calm]), strict=True)}
(root / "lab/results/vol_posthoc.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
