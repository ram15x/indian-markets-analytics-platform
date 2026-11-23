"""Forecast Lab, experiment 2. Protocol: docs/LAB_2_RETURN_RANGES.md (fixed before the run). Usage: python lab/range_forecast.py"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.series import build_all
warnings.filterwarnings("ignore")
H, STEP, WARM, TEST_FROM, ALPHA = 252, 21, 252, pd.Timestamp("2019-01-01"), 0.2
root = Path(__file__).parent.parent; rng = np.random.default_rng(7)

nav = pd.read_parquet(root / "data/nav_raw.parquet"); nav["date"] = pd.to_datetime(nav.date)
S = build_all(nav, pd.read_parquet(root / "data/dq_events.parquet"), pd.read_parquet(root / "data/dq_adjustments.parquet"))
rows = []
for c, s in S.items():
    d = pd.to_datetime(s.dates)
    if not (d[0] <= pd.Timestamp("2014-01-01") and d[-1] >= pd.Timestamp("2026-10-01")): continue
    r = np.diff(np.log(s.nav))
    if r[d[1:] >= pd.Timestamp("2015-01-01")].std(ddof=1) * np.sqrt(252) <= 0.08: continue
    n = len(r); cs = np.concatenate([[0], np.cumsum(r ** 2)]); lp = np.concatenate([[0], np.cumsum(r)]); peak = np.maximum.accumulate(lp)
    ew = np.empty(n); v = np.mean(r[:30] ** 2)
    for i in range(n): v = 0.94 * v + 0.06 * r[i] ** 2; ew[i] = v
    for t in range(WARM, n - H, STEP):
        def rvn(k, cs=cs, t=t): return np.sqrt(252 * (cs[t + 1] - cs[t + 1 - k]) / k)
        rows.append(dict(code=c, origin=d[t + 1], end=d[t + 1 + H], y=lp[t + 1 + H] - lp[t + 1], rv21=rvn(21), rv63=rvn(63), rv126=rvn(126),
                         ew=np.sqrt(252 * ew[t]), dd=peak[t + 1] - lp[t + 1], mom63=lp[t + 1] - lp[t + 1 - 63], mom252=lp[t + 1] - lp[t + 1 - 252]))
df = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(); df = df[(df.rv21 > 0) & (df.ew > 0)].reset_index(drop=True)
print("funds", df.code.nunique(), "origins", len(df), flush=True)
FE = ["rv21", "rv63", "rv126", "ew", "dd", "mom63", "mom252"]
import lightgbm as lgb
years = sorted(df[(df.origin >= TEST_FROM)].origin.dt.year.unique())
res = []
for Y in years:
    j1, j0 = pd.Timestamp(f"{Y}-01-01"), pd.Timestamp(f"{Y - 1}-01-01")
    fit, cal, allp = df[df.end < j0], df[(df.end >= j0) & (df.end < j1)], df[df.end < j1]
    te = df[df.origin.dt.year == Y].copy()
    if len(fit) < 2000 or len(cal) < 200 or len(te) == 0: continue
    lo_q, hi_q = ALPHA / 2, 1 - ALPHA / 2
    # B1 pooled empirical
    b1 = (allp.y.quantile(lo_q), allp.y.quantile(hi_q)); te["b1_l"], te["b1_u"] = b1
    # B2 per-fund empirical
    g = allp.groupby("code").y; cnt = g.count(); ql, qu = g.quantile(lo_q), g.quantile(hi_q)
    ok = te.code.map(cnt).fillna(0) >= 24
    te["b2_l"] = np.where(ok, te.code.map(ql), b1[0]); te["b2_u"] = np.where(ok, te.code.map(qu), b1[1])
    # B3 volatility-scaled
    z = allp.y / allp.ew; zl, zu = z.quantile(lo_q), z.quantile(hi_q); te["b3_l"], te["b3_u"] = te.ew * zl, te.ew * zu
    # M1 conformalised quantile LightGBM
    mk = lambda a: lgb.LGBMRegressor(objective="quantile", alpha=a, n_estimators=150, learning_rate=0.05, num_leaves=15, min_child_samples=200, random_state=7, verbose=-1, n_jobs=2)
    ml, mu = mk(lo_q).fit(fit[FE], fit.y), mk(hi_q).fit(fit[FE], fit.y)
    cl, cu = ml.predict(cal[FE]), mu.predict(cal[FE]); E = np.maximum(cl - cal.y.to_numpy(), cal.y.to_numpy() - cu)
    qhat = np.quantile(E, min(1.0, (1 - ALPHA) * (1 + 1 / len(E))))
    te["m1_l"], te["m1_u"] = ml.predict(te[FE]) - qhat, mu.predict(te[FE]) + qhat
    te["yr"] = Y; res.append(te)
T = pd.concat(res); T["month"] = T.origin.dt.to_period("M")
M = ["b1", "b2", "b3", "m1"]
for m in M:
    T[m + "_cov"] = ((T.y >= T[m + "_l"]) & (T.y <= T[m + "_u"])).astype(float); T[m + "_w"] = T[m + "_u"] - T[m + "_l"]
    T[m + "_is"] = T[m + "_w"] + (2 / ALPHA) * np.maximum(T[m + "_l"] - T.y, 0) + (2 / ALPHA) * np.maximum(T.y - T[m + "_u"], 0)
out = dict(funds=int(df.code.nunique()), test_rows=len(T), test_years=[int(y) for y in sorted(T.yr.unique())])
out["overall"] = {m: dict(coverage=float(T[m + "_cov"].mean()), width=float(T[m + "_w"].mean()), interval_score=float(T[m + "_is"].mean())) for m in M}
out["coverage_by_year"] = {m: {int(k): round(float(v), 3) for k, v in T.groupby("yr")[m + "_cov"].mean().items()} for m in M}
out["interval_score_by_year"] = {m: {int(k): round(float(v), 3) for k, v in T.groupby("yr")[m + "_is"].mean().items()} for m in M}
T["calm"] = T.rv63 < T.rv63.median()
out["coverage_by_regime"] = {m: {"calm": float(T[T.calm][m + "_cov"].mean()), "stressed": float(T[~T.calm][m + "_cov"].mean())} for m in M}
best = min(("b1", "b2", "b3"), key=lambda m: out["overall"][m]["interval_score"]); out["best_baseline"] = best
d = T.groupby("month").apply(lambda g: (g["m1_is"] - g[best + "_is"]).mean(), include_groups=False).to_numpy()
bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(5000)]
yrs_ok = sum(0.70 <= v <= 0.90 for v in out["coverage_by_year"]["m1"].values())
out["m1_vs_best_baseline"] = dict(mean_score_diff=float(d.mean()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], months=len(d), years_with_coverage_70_90=int(yrs_ok))
out["PASSES_RULE"] = bool(0.77 <= out["overall"]["m1"]["coverage"] <= 0.83 and yrs_ok >= 5 and np.percentile(bs, 97.5) < 0 and out["overall"]["m1"]["interval_score"] < out["overall"][best]["interval_score"])
Path(root / "lab/results").mkdir(exist_ok=True); (root / "lab/results/range_forecast_results.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
