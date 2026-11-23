"""Forecast Lab, experiment 4. Protocol: docs/LAB_4_PEER_EMBEDDINGS.md (fixed before the run). Usage: python lab/embedding_peers.py"""
import sys, re, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.series import build_all
warnings.filterwarnings("ignore")
root = Path(__file__).parent.parent
import torch, torch.nn as nn, torch.nn.functional as F
torch.manual_seed(7); np.random.seed(7); torch.set_num_threads(2); rng = np.random.default_rng(7)

RULES = [("overnight", r"overnight"), ("liquid", r"\bliquid\b"), ("ultra_short", r"ultra short|ultrashort"), ("money_market", r"money market"),
         ("short_dur", r"short duration|short term"), ("low_dur", r"low duration"), ("corp_bond", r"corporate bond"), ("gilt", r"\bgilt\b"),
         ("credit_risk", r"credit risk"), ("banking_psu", r"banking (and|&) psu"), ("dynamic_bond", r"dynamic bond"),
         ("large_mid", r"large (&|and) mid"), ("large_cap", r"large ?cap|blue ?chip|top 100"), ("mid_cap", r"(?<!large )(?<!large & )mid ?cap(?!.*small)"),
         ("small_cap", r"small ?cap"), ("flexi_cap", r"flexi ?cap"), ("multi_cap", r"multi ?cap"), ("elss", r"elss|tax saver|tax advantage|tax plan"),
         ("focused", r"focused"), ("value_contra", r"\bvalue\b|contra"), ("arbitrage", r"arbitrage"), ("gold", r"\bgold\b"), ("silver", r"\bsilver\b"),
         ("balanced_adv", r"balanced advantage|dynamic asset"), ("equity_savings", r"equity savings"), ("pharma_health", r"pharma|healthcare"),
         ("tech", r"technology|digital|\bit fund"), ("infra", r"infrastructure"), ("banking_fin", r"banking & financial|banking and financial|financial services")]
sc = pd.read_parquet(root / "data/schemes.parquet"); lab = {}
for c, nm in zip(sc.scheme_code, sc.scheme_name, strict=True):
    t = nm.lower()
    if "direct" not in t or "growth" not in t or re.search(r"idcw|dividend|bonus|payout|segregated", t): continue
    hit = [k for k, p in RULES if re.search(p, t)]
    if "banking_psu" in hit and "dynamic_bond" in hit: pass
    if len(hit) == 1: lab[c] = hit[0]
base = {c: re.sub(r"[^a-z0-9 ]", "", re.sub(r"direct|plan|growth|option|fund|-", " ", nm.lower())).split() for c, nm in zip(sc.scheme_code, sc.scheme_name, strict=True)}
base = {c: " ".join(w) for c, w in base.items()}

nav = pd.read_parquet(root / "data/nav_raw.parquet"); nav["date"] = pd.to_datetime(nav.date); nav = nav[nav.scheme_code.isin(lab)]
S = build_all(nav, pd.read_parquet(root / "data/dq_events.parquet"), pd.read_parquet(root / "data/dq_adjustments.parquet"))
R = pd.concat({c: pd.Series(np.diff(np.log(s.nav)), index=pd.to_datetime(s.dates)[1:]) for c, s in S.items() if len(s.nav) > 300}, axis=1)
cal = R.index[R.notna().sum(axis=1) >= 100]; R = R.loc[cal]
WIN = dict(train=("2015-01-01", "2019-10-31"), A=("2019-11-22", "2022-11-21"), B=("2022-11-22", "2025-11-21"))
def window(w):
    a, b = WIN[w]; X = R.loc[a:b]; ok = X.notna().mean() >= 0.98; X = X.loc[:, ok].fillna(0.0); return X
Xtr, XA, XB = window("train"), window("A"), window("B")
print({k: v.shape for k, v in dict(train=Xtr, A=XA, B=XB).items()}, "labelled funds in B:", XB.shape[1], flush=True)

class Enc(nn.Module):
    def __init__(s, d=64, patch=5):
        super().__init__(); s.p = patch; s.inp = nn.Linear(patch, d)
        s.tf = nn.TransformerEncoder(nn.TransformerEncoderLayer(d, 4, 128, 0.0, batch_first=True), 2); s.d = d
    def forward(s, x):                                    # x: (B, T) daily returns in percent
        B, T = x.shape; T = (T // s.p) * s.p; h = s.inp(x[:, :T].reshape(B, T // s.p, s.p))
        pos = torch.arange(h.shape[1])[:, None] / (10000 ** (torch.arange(0, s.d, 2) / s.d))[None]
        pe = torch.zeros(h.shape[1], s.d); pe[:, 0::2] = torch.sin(pos); pe[:, 1::2] = torch.cos(pos)
        return s.tf(h + pe).mean(1)
def embed(m, X):
    m.eval()
    with torch.no_grad(): return F.normalize(m(torch.tensor(X.T.to_numpy() * 100, dtype=torch.float32).clamp(-10, 10)), dim=1).numpy()
m0 = Enc(); E0 = (lambda X: embed(m0, X))                                      # random-weights control
m = Enc(); opt = torch.optim.AdamW(m.parameters(), 1e-3, weight_decay=1e-4); A_ = torch.tensor(Xtr.to_numpy() * 100, dtype=torch.float32).clamp(-10, 10); L, Nf = A_.shape[0], A_.shape[1]
for step in range(600):
    m.train(); idx = torch.tensor(rng.choice(Nf, size=min(128, Nf), replace=False)); s1 = rng.integers(0, L - 500, len(idx)); s2 = s1 + 250 + rng.integers(0, L - 500 - s1 + 1)
    a = torch.stack([A_[s:s + 250, i] for s, i in zip(s1, idx.tolist(), strict=True)]); b = torch.stack([A_[min(s, L - 250):min(s, L - 250) + 250, i] for s, i in zip(s2, idx.tolist(), strict=True)])
    z = F.normalize(torch.cat([m(a + 0.02 * torch.randn_like(a)), m(b + 0.02 * torch.randn_like(b))]), dim=1); n_ = len(idx)
    sim = z @ z.T / 0.1; sim.fill_diagonal_(-1e9); tgt = torch.cat([torch.arange(n_, 2 * n_), torch.arange(0, n_)])
    loss = F.cross_entropy(sim, tgt); opt.zero_grad(); loss.backward(); opt.step()
    if step % 150 == 0: print("step", step, round(float(loss), 3), flush=True)

def comp(X): return X.mean(axis=1).to_numpy()
def feats(X):
    c = comp(X); v = X.to_numpy(); cum = np.cumsum(v, 0); dd = (cum - np.maximum.accumulate(cum, 0)).min(0)
    sd = v.std(0, ddof=1) * np.sqrt(252); beta = (v * (c - c.mean())[:, None]).mean(0) / c.var(); cor = np.array([np.corrcoef(v[:, i], c)[0, 1] for i in range(v.shape[1])])
    z = (v - v.mean(0)) / (v.std(0) + 1e-12); sk = (z ** 3).mean(0); ku = (z ** 4).mean(0) - 3; dn = np.sqrt((np.minimum(v, 0) ** 2).mean(0)) * np.sqrt(252)
    M = np.column_stack([sd, beta, cor, sk, ku, dd, dn]); M = np.nan_to_num(M); return (M - M.mean(0)) / (M.std(0) + 1e-12)
def pca(X):
    v = X.to_numpy().T; v = (v - v.mean(1, keepdims=True)) / (v.std(1, keepdims=True) + 1e-12); u, s, _ = np.linalg.svd(v, full_matrices=False); return u[:, :16] * s[:16]
def sim_matrix(name, X):
    if name == "CORR": return np.corrcoef(X.to_numpy().T)
    if name == "FEAT": f = feats(X); d = ((f[:, None] - f[None]) ** 2).sum(-1); return -d
    if name == "PCA": f = pca(X); d = ((f[:, None] - f[None]) ** 2).sum(-1); return -d
    if name == "N": e = embed(m, X); return e @ e.T
    if name == "N0": e = embed(m0, X); return e @ e.T
def neighbours(Sm, codes, k=5):
    out = {}; cc = list(codes)
    for i, c in enumerate(cc):
        order = np.argsort(-Sm[i]); nb = [cc[j] for j in order if cc[j] != c and base[cc[j]] != base[c]][:k]; out[c] = nb
    return out
NAMES = ["CORR", "FEAT", "PCA", "N0", "N"]; res = {}; nbB = {}; nbA = {}
for nm in NAMES:
    nbB[nm] = neighbours(sim_matrix(nm, XB), XB.columns); nbA[nm] = neighbours(sim_matrix(nm, XA), XA.columns)
def prec(nb): return {c: np.mean([lab[x] == lab[c] for x in v]) for c, v in nb.items()}
P = {nm: prec(nbB[nm]) for nm in NAMES}; funds = list(XB.columns)
out = dict(windows=WIN, n_funds_B=len(funds), n_funds_A=XA.shape[1], n_train=Xtr.shape[1], categories=pd.Series([lab[c] for c in funds]).value_counts().to_dict())
out["precision_at_5"] = {nm: float(np.mean(list(P[nm].values()))) for nm in NAMES}
cats = pd.Series({c: lab[c] for c in funds}); out["precision_by_category"] = {nm: {k: round(float(np.mean([P[nm][c] for c in cats[cats == k].index])), 3) for k in cats.unique() if (cats == k).sum() >= 5} for nm in NAMES}
both = [c for c in funds if c in set(XA.columns)]
out["stability_top5_overlap_A_vs_B"] = {nm: float(np.mean([len(set(nbA[nm][c]) & set(nbB[nm][c])) / 5 for c in both])) for nm in NAMES}; out["n_both_windows"] = len(both)
best = max(("CORR", "FEAT", "PCA"), key=lambda k: out["precision_at_5"][k]); out["best_baseline"] = best
d = np.array([P["N"][c] - P[best][c] for c in funds]); bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(5000)]
d0 = np.array([P["N"][c] - P["N0"][c] for c in funds]); bs0 = [d0[rng.integers(0, len(d0), len(d0))].mean() for _ in range(5000)]
out["N_vs_best_baseline"] = dict(diff=float(d.mean()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
out["N_vs_random_control"] = dict(diff=float(d0.mean()), ci95=[float(np.percentile(bs0, 2.5)), float(np.percentile(bs0, 97.5))])
out["PASSES_RULE"] = bool(d.mean() >= 0.03 and np.percentile(bs, 2.5) > 0 and np.percentile(bs0, 2.5) > 0 and out["stability_top5_overlap_A_vs_B"]["N"] >= out["stability_top5_overlap_A_vs_B"][best])
Path(root / "lab/results").mkdir(exist_ok=True); (root / "lab/results/embedding_results.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
