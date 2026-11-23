"""Forecast Lab, experiment 1. Protocol: docs/LAB_1_VOLATILITY.md (fixed before the run). Usage: python lab/vol_forecast.py"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.series import build_all
warnings.filterwarnings("ignore")
H, STEP, WARM, TEST_FROM = 21, 21, 252, pd.Timestamp("2019-01-01")
root = Path(__file__).parent.parent
rng = np.random.default_rng(7)

nav = pd.read_parquet(root / "data/nav_raw.parquet"); nav["date"] = pd.to_datetime(nav.date)
S = build_all(nav, pd.read_parquet(root / "data/dq_events.parquet"), pd.read_parquet(root / "data/dq_adjustments.parquet"))
uni = {}
for c, s in S.items():
    d = pd.to_datetime(s.dates)
    if d[0] <= pd.Timestamp("2014-01-01") and d[-1] >= pd.Timestamp("2026-10-01"):
        r = np.diff(np.log(s.nav))
        if r[d[1:] >= pd.Timestamp("2015-01-01")].std(ddof=1) * np.sqrt(252) > 0.08: uni[c] = (d, r)
print("funds:", len(uni), flush=True)


def rv(x): return np.sqrt(252 * np.mean(np.square(x)))


rows = []   # one row per fund-origin
for c, (d, r) in uni.items():
    n = len(r)                      # r[i] is the return on d[i+1]
    cs = np.concatenate([[0], np.cumsum(r ** 2)])
    ew = np.empty(n); v = np.mean(r[:30] ** 2)
    for i in range(n): v = 0.94 * v + 0.06 * r[i] ** 2; ew[i] = v
    peak = np.maximum.accumulate(np.concatenate([[0], np.cumsum(r)]))
    lp = np.concatenate([[0], np.cumsum(r)])
    for t in range(WARM, n - H, STEP):          # origin = after return t has been observed (index t)
        def rvn(k, cs=cs, t=t): return np.sqrt(252 * (cs[t + 1] - cs[t + 1 - k]) / k)
        fut = np.sqrt(252 * (cs[t + 1 + H] - cs[t + 1]) / H)
        if fut <= 0: continue
        rows.append(dict(code=c, origin=d[t + 1], end=d[t + 1 + H], y=fut, rv5=rvn(5), rv21=rvn(21), rv63=rvn(63), rv126=rvn(126),
                         ew=np.sqrt(252 * ew[t]), absr=abs(r[t]) * np.sqrt(252), dd=peak[t + 1] - lp[t + 1], mom63=lp[t + 1] - lp[t + 1 - 63], i=t))
df = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=["rv5", "rv21", "rv63", "rv126", "y"])
df = df[(df.rv5 > 0) & (df.rv21 > 0) & (df.rv63 > 0) & (df.rv126 > 0)].reset_index(drop=True)
print("fund-origins:", len(df), flush=True)

# ---- GARCH(1,1)-t per fund, refit each January on data before it; forecast = mean variance over the next 21 days
from arch import arch_model
g_f = np.full(len(df), np.nan); g_fail = 0; used_fallback = 0
years = sorted(df[df.origin >= TEST_FROM].origin.dt.year.unique())
for c, (d, r) in uni.items():
    idx = df.index[df.code == c]
    if len(idx) == 0: continue
    for y in years:
        cut = np.searchsorted(d, pd.Timestamp(f"{y}-01-01"))
        sub = idx[(df.loc[idx, "origin"].dt.year == y).to_numpy()]
        if len(sub) == 0: continue
        try:
            res = arch_model(r[:cut - 1] * 100, mean="Zero", vol="GARCH", p=1, q=1, dist="t").fit(disp="off", show_warning=False)
            om, al, be = res.params["omega"], res.params["alpha[1]"], res.params["beta[1]"]
            ph = min(al + be, 0.9999); V = om / (1 - ph)
            sig = np.empty(len(r) + 1); sig[0] = np.var(r[:cut - 1] * 100)
            for i in range(len(r)): sig[i + 1] = om + al * (r[i] * 100) ** 2 + be * sig[i]
            for k in sub:
                t = int(df.at[k, "i"]); s_next = sig[t + 1]          # variance for the day after the origin
                avg = V + (s_next - V) * (1 - ph ** H) / (H * (1 - ph))
                g_f[k] = np.sqrt(252 * avg) / 100
        except Exception:
            g_fail += 1
df["garch"] = g_f
fb = df.garch.isna(); used_fallback = int((fb & (df.origin >= TEST_FROM)).sum()); df.loc[fb, "garch"] = df.loc[fb, "ew"]

# ---- pooled log-models refit each January using only targets that ended before it (21-day purge)
import lightgbm as lgb
FE = ["rv5", "rv21", "rv63", "rv126", "ew", "absr", "dd", "mom63"]
X = lambda a: np.log(a[["rv5", "rv21", "rv63"]].clip(lower=1e-6)).to_numpy()
XL = lambda a: np.column_stack([np.log(a[["rv5", "rv21", "rv63", "rv126", "ew"]].clip(lower=1e-6)).to_numpy(), a[["absr", "dd", "mom63"]].to_numpy()])
df["har"] = np.nan; df["lgbm"] = np.nan
for y in years:
    tr = df[df.end < pd.Timestamp(f"{y}-01-01")]; te = df.index[df.origin.dt.year == y]
    A = np.column_stack([np.ones(len(tr)), X(tr)]); b = np.linalg.lstsq(A, np.log(tr.y.to_numpy()), rcond=None)[0]
    df.loc[te, "har"] = np.exp(np.column_stack([np.ones(len(te)), X(df.loc[te])]) @ b)
    m = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=15, min_child_samples=200, random_state=7, verbose=-1, n_jobs=2).fit(XL(tr), np.log(tr.y.to_numpy()))
    df.loc[te, "lgbm"] = np.exp(m.predict(XL(df.loc[te])))
df["b1"], df["b2"], df["b3"] = df.rv21, df.rv63, df.ew

T = df[df.origin >= TEST_FROM].copy(); T["yr"] = T.origin.dt.year
METH = ["b1", "b2", "b3", "har", "garch", "lgbm"]
qlike = lambda f, y: np.log(f ** 2) + (y ** 2) / (f ** 2)
for m in METH: T["q_" + m] = qlike(T[m], T.y); T["a_" + m] = (T[m] - T.y).abs()
out = dict(funds=len(uni), test_rows=len(T), garch_failed_fits=g_fail, garch_origins_using_ewma_fallback=used_fallback, years=[int(v) for v in years])
out["overall"] = {m: dict(qlike=float(T["q_" + m].mean()), mae=float(T["a_" + m].mean())) for m in METH}
out["by_year_qlike"] = {m: {int(k): float(v) for k, v in T.groupby("yr")["q_" + m].mean().items()} for m in METH}
pf = T.groupby("code")
out["share_of_funds_beating_har"] = {m: float((pf["q_" + m].mean() < pf["q_har"].mean()).mean()) for m in METH if m != "har"}
fm = pd.DataFrame({m: pf["q_" + m].mean() for m in METH})
ver = {}
for m in ("garch", "lgbm", "b1", "b2", "b3"):
    diff = (fm[m] - fm["har"]).to_numpy(); bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(4000)]
    wins = sum(out["by_year_qlike"][m][y] < out["by_year_qlike"]["har"][y] for y in out["years"] if y in out["by_year_qlike"][m])
    ver[m] = dict(diff_vs_har=float(diff.mean()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], years_better=int(wins), of_years=len(out["years"]),
                  PASSES_RULE=bool(out["overall"][m]["qlike"] < out["overall"]["har"]["qlike"] and wins >= 6 and np.percentile(bs, 97.5) < 0))
out["vs_har"] = ver
Path(root / "lab/results").mkdir(exist_ok=True); T.to_parquet(root / "lab/results/vol_forecast_rows.parquet")
(root / "lab/results/vol_forecast_results.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out["overall"], indent=1)); print(json.dumps(ver, indent=1)); print({k: out[k] for k in ("funds", "test_rows", "garch_failed_fits", "garch_origins_using_ewma_fallback")})
print(json.dumps(out["by_year_qlike"]["har"])); print(json.dumps(out["share_of_funds_beating_har"]))
