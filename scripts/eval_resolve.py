"""Score name resolution on generated queries. Usage: eval_resolve.py dev|locked (locked refused twice)."""
import sys, json, math; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from imap.resolve_v1 import Resolver, core_tokens

split = sys.argv[1]; assert split in ("dev", "locked")
root = Path(__file__).parent.parent / "data"; lock = root / "resolve_eval_locked.json"
if split == "locked" and lock.exists(): sys.exit("locked already scored")
S = pd.read_parquet(root / "schemes.parquet"); codes = S.scheme_code.values; names = S.scheme_name.tolist()
R = Resolver(codes, names)
toks = [core_tokens(n) for n in names]; tokset = [set(t) for t in toks]
rng = np.random.default_rng(1122 if split == "dev" else 1123)
pool = [i for i, c in enumerate(codes) if (c % 2 == 0) == (split == "dev")]
pick = rng.choice(pool, 400, replace=False)
KNOWN = {"icici prudential": "icici pru", "aditya birla sun life": "absl", "nippon india": "nippon"}
UNSEEN = {"kotak mahindra": "kotak", "sbi mutual": "sbi", "hdfc mutual": "hdfc"}

def typo(words):
    ok = [i for i, w in enumerate(words) if len(w) >= 5]
    if not ok: return words
    i = ok[rng.integers(len(ok))]; w = words[i]; p = int(rng.integers(1, len(w) - 1)); k = rng.integers(3)
    w = (w[:p] + "x" + w[p + 1:]) if k == 0 else (w[:p] + w[p + 1:]) if k == 1 else (w[:p] + w[p + 1] + w[p] + w[p + 2:])
    out = list(words); out[i] = w; return out

rows = []
for i in pick:
    t = toks[i]; typ = ["plain", "alias_known", "alias_unseen", "typo", "short"][rng.integers(5)]
    clean = list(t); q = " ".join(t)
    if typ == "alias_known" or typ == "alias_unseen":
        d = KNOWN if typ == "alias_known" else UNSEEN; hit = None; s = " ".join(t)
        if typ == "alias_known":
            for l, a in d.items():
                if s.startswith(l): q = a + s[len(l):]; hit = 1; break
        else:  # prepend a long form to the AMC word; unseen alias must be learned from the long form, so use the short form only
            for l, a in d.items():
                if t and t[0] == a: q = a + " " + " ".join(t[1:]); hit = 1; break
        if hit is None: typ = "plain"; q = " ".join(t)
    elif typ == "typo": q = " ".join(typo(t))
    elif typ == "short":
        k = max(2, math.ceil(0.6 * len(t))); keep = sorted(rng.choice(len(t), min(k, len(t)), replace=False)); clean = [t[j] for j in keep]; q = " ".join(clean)
    truth = [j for j in range(len(names)) if set(clean) <= tokset[j]]
    full = (set(clean) == tokset[i]) and sum(1 for j in range(len(names)) if tokset[j] == tokset[i]) == 1   # Amendment 1
    r = R.resolve(q)
    rows.append(dict(typ=typ, q=q, src=int(codes[i]), n_truth=(1 if full else len(truth)), res=r.status, got=r.code,
                     in5=int(codes[i]) in [c[0] for c in r.candidates]))
D = pd.DataFrame(rows); D["unique"] = D.n_truth == 1
U = D[D.unique]; A = D[~D.unique]; out = {"split": split, "n": len(D), "unique": len(U), "ambiguous": len(A)}
out["confident_wrong_on_unique"] = float(((U.res == "RESOLVED") & (U.got != U.src)).mean())
out["overconfident_on_ambiguous"] = float((A.res == "RESOLVED").mean()) if len(A) else None
for typ in ["plain", "alias_known", "alias_unseen", "typo", "short"]:
    u = U[U.typ == typ]
    out[f"coverage_{typ}"] = (float(((u.res == "RESOLVED") & (u.got == u.src)).mean()), len(u)) if len(u) else None
cl = U[U.res == "CLARIFY"]; out["clarify_true_in_top5"] = float(cl.in5.mean()) if len(cl) else None
a_small = A[(A.n_truth <= 5)]; out["ambiguous_small_clarify_has_true"] = float(((a_small.res == "CLARIFY") & a_small.in5).mean()) if len(a_small) else None
print(json.dumps(out, indent=1))
(lock if split == "locked" else root / "resolve_eval_dev.json").write_text(json.dumps(out, indent=1))
if split == "dev":
    bad = U[(U.res == "RESOLVED") & (U.got != U.src)]; print("CONFIDENT WRONG:\n", bad[["typ", "q", "src", "got"]].head(10).to_string())
    miss = U[(U.res == "CLARIFY")]; print("CLARIFY on unique (sample):\n", miss[["typ", "q", "in5"]].head(12).to_string())
