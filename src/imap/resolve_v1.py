"""Fund-name resolution: spell-corrected word matching plus char n-gram TF-IDF, with a clarify rule."""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

STOP = {"fund", "plan", "option", "direct", "growth", "scheme", "the", "mutual", "mf"}
ALIASES = {  # alias -> canonical (KNOWN set; document any change in RESOLVE_EVAL.md)
    "icici pru": "icici prudential", "absl": "aditya birla sun life", "nippon": "nippon india",
}
TAU = 0.50
MARGIN = 0.05


def core_tokens(name: str) -> list[str]:
    name = re.sub(r"\(.*?\)", " ", name.lower())
    return [t for t in re.findall(r"[a-z0-9&]+", name) if t not in STOP]


def _expand(s: str) -> str:
    for a, c in ALIASES.items():
        rest = c[len(a):] if c.startswith(a) else None
        pat = rf"\b{re.escape(a)}\b" + (rf"(?!{re.escape(rest)}\b)" if rest else "")
        s = re.sub(pat, c, s)
    return s


def query_tokens(q: str) -> list[str]:
    s = _expand(" ".join(re.findall(r"[a-z0-9&]+", q.lower())))
    return [t for t in s.split() if t not in STOP]


def _edit(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap: return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@dataclass
class Resolution:
    status: str                 # RESOLVED | CLARIFY
    code: int | None
    candidates: list            # [(code, name, score)] best first (up to 5)
    why: str = ""
    corrected: str = ""


class Resolver:
    def __init__(self, codes, names, tau=TAU, margin=MARGIN):
        self.codes = np.asarray(codes); self.names = list(names); self.tau = tau; self.margin = margin
        self.toks = [core_tokens(n) for n in self.names]; self.sets = [frozenset(t) for t in self.toks]
        self.df = Counter(w for s in self.sets for w in s)
        self.vocab = sorted(self.df)
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.M = self.vec.fit_transform([" ".join(t) for t in self.toks])

    def _correct(self, w: str) -> str:
        if w in self.df or w.isdigit() or len(w) < 4: return w
        cap = 1 if len(w) <= 6 else 2
        best = [(self._d(w, v, cap), -self.df[v], v) for v in self.vocab]
        best = [b for b in best if b[0] <= cap]
        return min(best)[2] if best else w

    @staticmethod
    def _d(a, b, cap): return _edit(a, b, cap)

    def resolve(self, query: str) -> Resolution:
        qt = [self._correct(w) for w in query_tokens(query)]
        if not qt:
            return Resolution("CLARIFY", None, [], "empty query")
        q = " ".join(qt); qs = set(qt)
        sc = (self.M @ self.vec.transform([q]).T).toarray().ravel()
        rank = lambda idx: [(int(self.codes[i]), self.names[i], float(sc[i])) for i in sorted(idx, key=lambda i: -sc[i])[:5]]
        exact = [i for i, s in enumerate(self.sets) if s == qs]
        if len(exact) == 1:
            return Resolution("RESOLVED", int(self.codes[exact[0]]), rank(exact), "full name match", q)
        contain = [i for i, s in enumerate(self.sets) if qs <= s]
        if len(contain) == 1:
            return Resolution("RESOLVED", int(self.codes[contain[0]]), rank(contain), "only scheme containing all words", q)
        if len(contain) >= 2:
            return Resolution("CLARIFY", None, rank(contain), f"{len(contain)} schemes contain all words", q)
        top = np.argsort(-sc)[:5]; cand = rank(top)
        if sc[top[0]] >= self.tau and (sc[top[0]] - sc[top[1]]) >= self.margin:
            return Resolution("RESOLVED", cand[0][0], cand, "closest by character match", q)
        return Resolution("CLARIFY", None, cand, "no clear match", q)
