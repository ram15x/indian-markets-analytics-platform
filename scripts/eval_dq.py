"""Score the data-quality layer on injected anomalies. Usage: eval_dq.py dev|locked
Locked set can be scored once; a second run is refused."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap import dq

split = sys.argv[1]; assert split in ("dev", "locked")
root = Path(__file__).parent.parent
lock = root / "data" / "dq_eval_locked.json"
if split == "locked" and lock.exists():
    sys.exit("locked set already scored; see data/dq_eval_locked.json")

nav = pd.read_parquet(root / "data" / "nav_raw.parquet")
g = {int(c): (x.date.values.astype("datetime64[D]"), x.nav.values.astype(float)) for c, x in nav.groupby("scheme_code")}
clean = []
for c, (d, v) in g.items():
    r = v[1:] / v[:-1]
    if len(v) >= 1000 and np.all(np.abs(r - 1) < 0.10) and np.all(v > 0):
        clean.append(c)
clean = sorted(c for c in clean if (c % 2 == 0) == (split == "dev"))
rng = np.random.default_rng(20261122 if split == "dev" else 20261123)
pick = rng.choice(clean, size=min(300, len(clean)), replace=False)
TYPES = ["scale", "bad", "transient", "persistent", "none"]

def near_clean(f):
    return any(abs(f / k - 1) <= 0.03 or abs(f * k - 1) <= 0.03 for k in dq.CLEAN_K)

rows = []
for c in pick:
    d, v0 = g[int(c)]; v = v0.copy(); n = len(v)
    typ = TYPES[rng.integers(len(TYPES))]
    t = int(rng.integers(100, n - 100)); truth = dict(type=typ, t=t); k = None; dirn = None
    if typ == "scale":
        k = float(rng.choice(dq.CLEAN_K)); dirn = int(rng.choice([-1, 1]))
        v[t:] *= (k if dirn == 1 else 1 / k)
    elif typ == "bad":
        f = float(np.exp(rng.uniform(np.log(1.3), np.log(3)))) if rng.random() < .5 else float(np.exp(rng.uniform(np.log(.33), np.log(.77))))
        v[t] *= f
    elif typ == "transient":
        L = int(rng.integers(3, 31)); f = float(rng.uniform(.6, .85)); v[t:t + L] *= f
    elif typ == "persistent":
        while True:
            f = float(rng.uniform(.55, .85)) if rng.random() < .5 else float(rng.uniform(1.15, 1.45))
            if not near_clean(f): break
        v[t:] *= f
    ev, ad = dq.run(pd.DataFrame(dict(scheme_code=int(c), date=d, nav=v)))
    core = ev[~ev.kind.isin(["STALE_RUN", "GAP"])] if len(ev) else ev
    out = dict(code=int(c), type=typ, n_core=len(core), n_adj=len(ad))
    hit = core[core.date == d[t]] if len(core) else core
    out["kinds_at_t"] = list(hit.kind) if len(hit) else []
    if typ == "scale":
        out["k_ok"] = bool(len(ad) == 1 and ad.k.iloc[0] == k)
        adj = dq.apply(pd.DataFrame(dict(scheme_code=int(c), date=d, nav=v)), ev, ad)
        target = v0 * (k if dirn == 1 else 1 / k)
        out["rel_err"] = float(np.nanmax(np.abs(adj.nav_adj.values / target - 1)))
    out.update(k=k, dirn=dirn, t=t, f=(float(f) if typ in ("bad","persistent","transient") else None), L=(L if typ=="transient" else None)); rows.append(out)
R = pd.DataFrame(rows)
res = {"split": split, "n": len(R), "types": R.type.value_counts().to_dict()}
sc = R[R.type == "scale"]
res["scale_recall"] = float(np.mean(["SCALE_CHANGE" in x for x in sc.kinds_at_t]))
res["scale_k_exact"] = float(sc.k_ok.mean())
res["scale_max_rel_err"] = float(sc.rel_err.max())
res["adjustments_emitted"] = int(R.n_adj.sum())
res["adjustments_true_scale"] = int(sc.n_adj.sum())
res["scale_precision"] = float(sc.n_adj.sum() / max(1, R.n_adj.sum()))
res["bad_recall"] = float(np.mean(["BAD_VALUE" in x for x in R[R.type == "bad"].kinds_at_t]))
res["transient_recall"] = float(np.mean(["TRANSIENT_SHIFT" in x for x in R[R.type == "transient"].kinds_at_t]))
pr = R[R.type == "persistent"]
res["persistent_flagged_large_move"] = float(np.mean(["LARGE_MOVE" in x for x in pr.kinds_at_t]))
res["persistent_over_corrected"] = int((pr.n_adj > 0).sum())
nn = R[R.type == "none"]
res["none_with_any_event"] = int((nn.n_core > 0).sum()); res["none_with_adjustment"] = int((nn.n_adj > 0).sum())
res["extra_events_outside_t"] = int(((R.n_core - R.kinds_at_t.map(len)).clip(lower=0)).sum())
print(json.dumps(res, indent=1))
if split == "locked":
    lock.write_text(json.dumps(res, indent=1))
else:
    (root / "data" / "dq_eval_dev.json").write_text(json.dumps(res, indent=1))
    print(R[(R.type == "scale") & ~R.kinds_at_t.map(lambda x: "SCALE_CHANGE" in x)].to_string()); print(R[(R.type == "transient") & ~R.kinds_at_t.map(lambda x: "TRANSIENT_SHIFT" in x)][["code","kinds_at_t","f","L","t"]].to_string())
