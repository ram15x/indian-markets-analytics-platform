"""Score resolver v2. Usage: eval_resolve_v2.py dev|locked (locked refused twice)."""
import sys, json, math; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from imap.resolve import Resolver, former_names
from imap.resolve_v1 import core_tokens

split = sys.argv[1]; assert split in ("dev", "locked")
root = Path(__file__).parent.parent / "data"; lock = root / "resolve_v2_eval_locked.json"
if split == "locked" and lock.exists(): sys.exit("locked already scored")
S = pd.read_parquet(root / "schemes.parquet"); RN = pd.read_csv(root / "renames.csv")
codes = S.scheme_code.values; names = S.scheme_name.tolist(); R = Resolver(codes, names, RN)
toks = [core_tokens(n) for n in names]; tokset = [set(t) for t in toks]
want = 0 if split == "dev" else 1
rng = np.random.default_rng(2301 if split == "dev" else 2302)
pool = [i for i, c in enumerate(codes) if c % 3 == want]
pick = rng.choice(pool, 400, replace=False)
KNOWN = {"icici prudential": "icici pru", "aditya birla sun life": "absl", "nippon india": "nippon"}

def typo(words):
    ok = [i for i, w in enumerate(words) if len(w) >= 5]
    if not ok: return words
    i = ok[rng.integers(len(ok))]; w = words[i]; p = int(rng.integers(1, len(w) - 1)); k = rng.integers(3)
    w = (w[:p] + "x" + w[p + 1:]) if k == 0 else (w[:p] + w[p + 1:]) if k == 1 else (w[:p] + w[p + 1] + w[p] + w[p + 2:])
    out = list(words); out[i] = w; return out

rows = []
for i in pick:
    t = toks[i]; typ = ["plain", "alias_known", "typo", "short"][rng.integers(4)]; clean = list(t); q = " ".join(t)
    if typ == "alias_known":
        s = " ".join(t); hit = False
        for l, a in KNOWN.items():
            if s.startswith(l): q = a + s[len(l):]; hit = True; break
        if not hit: typ = "plain"
    elif typ == "typo": q = " ".join(typo(t))
    elif typ == "short":
        k = max(2, math.ceil(0.6 * len(t))); keep = sorted(rng.choice(len(t), min(k, len(t)), replace=False)); clean = [t[j] for j in keep]; q = " ".join(clean)
    truth = [j for j in range(len(names)) if set(clean) <= tokset[j]]
    full = (set(clean) == tokset[i]) and sum(1 for j in range(len(names)) if tokset[j] == tokset[i]) == 1
    amc = toks[i][0] in set(clean) if typ != "typo" else True   # typo keeps all words (the AMC word may be mis-spelt but is present)
    r = R.resolve(q)
    rows.append(dict(typ=typ, q=q, src=int(codes[i]), n_truth=(1 if full else len(truth)), amc=amc, res=r.status, got=r.code,
                     in5=int(codes[i]) in [c[0] for c in r.candidates]))
D = pd.DataFrame(rows); out = {"split": split, "n": len(D)}
out["resolved_wrong_total"] = int(((D.res == "RESOLVED") & (D.got != D.src)).sum())
P = D[D.amc & (D.n_truth == 1)]
for typ in ["plain", "alias_known", "typo", "short"]:
    u = P[P.typ == typ]; out[f"coverage_amc_present_{typ}"] = (float(((u.res == "RESOLVED") & (u.got == u.src)).mean()), len(u)) if len(u) else None
N = D[~D.amc]; out["amc_absent"] = len(N); out["amc_absent_resolved"] = int((N.res == "RESOLVED").sum())
Ns = N[N.n_truth <= 5]; out["amc_absent_small_true_in_top5"] = (float(Ns.in5.mean()), len(Ns)) if len(Ns) else None
A = D[D.n_truth >= 2]; out["ambiguous"] = len(A); out["ambiguous_resolved"] = int((A.res == "RESOLVED").sum())

# rename set
items = []
for i, n in enumerate(names):
    for f in former_names(n):
        items.append((int(codes[i]), f, "archive"))
for _, r in RN.iterrows(): items.append((int(r.target_code), r.old_name, "sourced"))
items = sorted(items); mine = [x for k, x in enumerate(items) if (k % 2 == 0) == (split == "dev")]
rr = []
for code, old, kind in mine:
    variants = [old] + ([names[list(codes).index(code)].split()[0] + " " + old] if kind == "archive" else [])
    for v in variants:
        r = R.resolve(v); ok_res = r.status == "RESOLVED" and r.code == code; wrong = r.status == "RESOLVED" and r.code != code
        ok_cl = r.status == "CLARIFY" and code in [c[0] for c in r.candidates]
        rr.append(dict(kind=kind, q=v, outcome="RESOLVED_CORRECT" if ok_res else "RESOLVED_WRONG" if wrong else "CLARIFY_TRUE_IN_TOP5" if ok_cl else "CLARIFY_MISS"))
RR = pd.DataFrame(rr); out["rename_n"] = len(RR); out["rename_outcomes"] = RR.outcome.value_counts().to_dict()
out["rename_ok_rate"] = float(RR.outcome.isin(["RESOLVED_CORRECT", "CLARIFY_TRUE_IN_TOP5"]).mean())

# regression (the five v1 failures)
bad_v1 = {"axis bluechip": 130000, "hdfc top 100": None, "icici pru bluechip": None, "kotak emerging equity": None, "hdfc nifty 50 index": None}
reg = {}
for q in bad_v1:
    r = R.resolve(q); reg[q] = (r.status, r.candidates[0][1][:60] if r.candidates else "")
out["regression"] = reg
print(json.dumps(out, indent=1))
(lock if split == "locked" else root / "resolve_v2_eval_dev.json").write_text(json.dumps(out, indent=1))
if split == "dev":
    print(D[(D.res == "RESOLVED") & (D.got != D.src)][["typ", "q", "src", "got"]].to_string())
    print(RR[~RR.outcome.isin(["RESOLVED_CORRECT", "CLARIFY_TRUE_IN_TOP5"])].to_string())
