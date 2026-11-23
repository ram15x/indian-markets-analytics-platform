"""Forecast Lab, experiment 3. Protocol: docs/LAB_3_REGIMES.md (fixed before the run). Usage: python lab/regime_detection.py"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.series import build_all
from hmmlearn.hmm import GaussianHMM
warnings.filterwarnings("ignore")
root = Path(__file__).parent.parent; H = 21

nav = pd.read_parquet(root / "data/nav_raw.parquet"); nav["date"] = pd.to_datetime(nav.date)
S = build_all(nav, pd.read_parquet(root / "data/dq_events.parquet"), pd.read_parquet(root / "data/dq_adjustments.parquet"))
parts = []
for c, s in S.items():
    d = pd.to_datetime(s.dates)
    if not (d[0] <= pd.Timestamp("2014-01-01") and d[-1] >= pd.Timestamp("2026-10-01")): continue
    r = np.diff(np.log(s.nav))
    if r[d[1:] >= pd.Timestamp("2015-01-01")].std(ddof=1) * np.sqrt(252) <= 0.08: continue
    parts.append(pd.Series(r, index=d[1:], name=c))
W = pd.concat(parts, axis=1); W = W[W.index >= "2014-01-01"]
comp = W[W.notna().sum(axis=1) >= 100].mean(axis=1)
print("composite days", len(comp), comp.index[0].date(), comp.index[-1].date(), flush=True)
r = comp.to_numpy(); idx = comp.index; n = len(r)
cs = np.concatenate([[0], np.cumsum(r ** 2)]); lp = np.concatenate([[0], np.cumsum(r)])
fv = np.full(n, np.nan); fr = np.full(n, np.nan); fd = np.full(n, np.nan)
for t in range(n - H):
    fv[t] = np.sqrt(252 * (cs[t + 1 + H] - cs[t + 1]) / H); fr[t] = lp[t + 1 + H] - lp[t + 1]
    seg = lp[t + 1: t + 2 + H] - lp[t + 1]; fd[t] = (seg - np.maximum.accumulate(seg)).min()
tv = np.full(n, np.nan)
for t in range(20, n): tv[t] = np.sqrt(252 * (cs[t + 1] - cs[t - 20]) / 21)


def filtered(m, X):
    ll = m._compute_log_likelihood(X); a = np.empty((len(X), m.n_components)); p = m.startprob_ * np.exp(ll[0] - ll[0].max())
    p = p / p.sum(); a[0] = p
    for k in range(1, len(X)):
        p = (a[k - 1] @ m.transmat_) * np.exp(ll[k] - ll[k].max()); a[k] = p / p.sum()
    return a


years = [y for y in sorted(set(idx.year)) if y >= 2019]
lab_h = np.full(n, -1); lab_t = np.full(n, -1)
for Y in years:
    tr = np.where(idx < pd.Timestamp(f"{Y}-01-01"))[0]; te = np.where(idx.year == Y)[0]
    X = (r[tr] * 100).reshape(-1, 1); best = None
    for seed in range(10):
        m = GaussianHMM(3, covariance_type="diag", n_iter=200, random_state=seed).fit(X)
        sc = m.score(X)
        if best is None or sc > best[0]: best = (sc, m)
    m = best[1]; order = np.argsort(m.covars_.ravel()); rank = np.empty(3, int); rank[order] = np.arange(3)
    # filter from the start of training through the test year so the state at the first test day is informed by the past
    path = np.arange(0, te[-1] + 1); a = filtered(m, (r[path] * 100).reshape(-1, 1))
    lab_h[te] = rank[a[te].argmax(axis=1)]
    c1, c2 = np.nanpercentile(tv[tr], [100 / 3, 200 / 3]); lab_t[te] = np.where(tv[te] < c1, 0, np.where(tv[te] < c2, 1, 2))
ok = (lab_h >= 0) & ~np.isnan(fv)
D = pd.DataFrame(dict(date=idx, hmm=lab_h, tri=lab_t, fv=fv, fr=fr, fd=fd, yr=idx.year))[ok]
out = dict(composite_days=int(n), test_years=years)
for name in ("hmm", "tri"):
    g = D.groupby(name); out[name] = dict(days=g.size().to_dict(), fwd_vol=g.fv.mean().round(4).to_dict(), fwd_ret=g.fr.mean().round(4).to_dict(), fwd_worst_dd=g.fd.mean().round(4).to_dict())
    v = g.fv.mean(); out[name]["strictly_increasing"] = bool(len(v) == 3 and v[0] < v[1] < v[2]); out[name]["stressed_to_calm_vol_ratio"] = float(v.iloc[-1] / v.iloc[0])
    sw = []; 
    for Y in years:
        L = (lab_h if name == "hmm" else lab_t)[idx.year == Y]; sw.append(int((np.diff(L) != 0).sum()))
    out[name]["label_switches_per_year"] = float(np.mean(sw)); out[name]["switches_by_year"] = dict(zip(years, sw, strict=True))
okyrs = 0; tested = 0; detail = {}
for Y in years:
    g = D[D.yr == Y].groupby("hmm"); cnt = g.size(); keep = cnt[cnt >= 10].index
    if len(keep) >= 2:
        v = g.fv.mean()[keep]; tested += 1; good = bool(v.is_monotonic_increasing); okyrs += good; detail[int(Y)] = dict(states=[int(k) for k in keep], fwd_vol=[round(float(x), 3) for x in v], ordered=good)
out["year_checks"] = dict(tested=tested, ordered=okyrs, detail=detail)
h = out["hmm"]; t = out["tri"]
out["PASSES_RULE"] = bool(h["strictly_increasing"] and tested > 0 and okyrs / tested >= 0.75 and h["stressed_to_calm_vol_ratio"] >= 1.25 and h["stressed_to_calm_vol_ratio"] > t["stressed_to_calm_vol_ratio"] and h["label_switches_per_year"] < t["label_switches_per_year"])
Path(root / "lab/results").mkdir(exist_ok=True); (root / "lab/results/regime_results.json").write_text(json.dumps(out, indent=1, default=str)); print(json.dumps(out, indent=1, default=str))
