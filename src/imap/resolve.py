"""Fund-name resolution v2.

RESOLVE only when one scheme matches by words AND the query names its AMC (leading word of the
current name or of a former name). Everything else is CLARIFY. Character similarity only ranks
candidates. Former names come from the scheme name text and from data/renames.csv.
"""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from .resolve_v1 import STOP, core_tokens, query_tokens


def _edit(a: str, b: str, cap: int) -> int:
    """Damerau-Levenshtein (optimal string alignment): a swap of two adjacent letters costs 1."""
    if abs(len(a) - len(b)) > cap: return cap + 1
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1): d[i][0] = i
    for j in range(len(b) + 1): d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            c = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]

COMMON_WORDS = frozenset({'bank', 'old', 'wealth', 'trust', 'choice', 'ask', 'angel', 'union'})  # everyday words, not checked
COVER = 0.75
SHORT_MISSING, SHORT_COVER = 2, 0.5   # v3: short names such as 'axis elss'   # a non-exact match must use at least this share of the scheme's name words (v2 Amendment 1)
_FORMER = re.compile(r"\((?:formerly known as|formerly|erstwhile|earlier known as|previously known as)\s+([^)]*)\)?", re.I)


def former_names(name: str) -> list[str]:
    return [m.strip() for m in _FORMER.findall(name)]


@dataclass
class Resolution:
    status: str                 # RESOLVED | CLARIFY
    code: int | None
    candidates: list            # [(code, name, score)] best first (up to 5)
    why: str = ""
    corrected: str = ""


class Resolver:
    def __init__(self, codes, names, renames: pd.DataFrame | None = None):
        self.codes = np.asarray(codes); self.names = list(names)
        base = [core_tokens(n) for n in self.names]
        self.base = [frozenset(t) for t in base]
        self.lead = [t[0] if t else "" for t in base]
        old: list[list[list[str]]] = [[] for _ in self.names]   # former names as token lists
        for i, n in enumerate(self.names):
            for f in former_names(n):
                t = [w for w in re.findall(r"[a-z0-9&]+", f.lower()) if w not in STOP]
                if t: old[i].append(t)
        idx = {int(c): i for i, c in enumerate(self.codes)}
        if renames is not None:
            for _, r in renames.iterrows():
                j = idx.get(int(r.target_code))
                if j is not None:
                    i = j
                    t = [w for w in re.findall(r"[a-z0-9&]+", r.old_name.lower()) if w not in STOP]
                    if t: old[i].append(t)
        self.old = old
        self.leads = [{self.lead[i]} for i in range(len(self.names))]
        self.amc_words = frozenset(w for w in self.lead if w and not w.isdigit()) - COMMON_WORDS   # current AMC word only (see v2 Amendment 1)
        # containment sets: current words plus every former-name word
        self.union = [self.base[i].union(*[set(t) for t in old[i]]) if old[i] else self.base[i] for i in range(len(self.names))]
        self.exact_sets = [[self.base[i]] + [frozenset(t) for t in old[i]] for i in range(len(self.names))]
        self.df = Counter(w for s in self.union for w in s)
        self.vocab = sorted(self.df)
        docs = [" ".join(base[i]) + " " + " ".join(" ".join(t) for t in old[i]) for i in range(len(self.names))]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.M = self.vec.fit_transform(docs)

    def _correct(self, w: str) -> str:
        if w in self.df or w.isdigit() or len(w) < 4: return w
        cap = 1 if len(w) <= 6 else 2
        best = [(_edit(w, v, cap), -self.df[v], v) for v in self.vocab]
        best = [b for b in best if b[0] <= cap]
        return min(best)[2] if best else w

    def resolve(self, query: str) -> Resolution:
        qt = [self._correct(w) for w in query_tokens(query)]
        if not qt:
            return Resolution("CLARIFY", None, [], "empty query")
        q = " ".join(qt); qs = set(qt)
        sc = (self.M @ self.vec.transform([q]).T).toarray().ravel()
        rank = lambda idx: [(int(self.codes[i]), self.names[i], float(sc[i])) for i in sorted(idx, key=lambda i: -sc[i])[:5]]
        exact = [i for i, ss in enumerate(self.exact_sets) if any(s == qs for s in ss)]
        contain = [i for i, s in enumerate(self.union) if qs <= s]
        pool = exact if exact else contain
        if len(pool) == 1:
            i = pool[0]
            covered = len(qs & self.base[i]) / max(1, len(self.base[i]))
            missing = len(self.base[i] - qs)
            if self.leads[i] & qs and (exact or covered >= COVER or (missing <= SHORT_MISSING and covered >= SHORT_COVER)):
                return Resolution("RESOLVED", int(self.codes[i]), rank(pool), "full name match" if exact else "only scheme containing all words", q)
            return Resolution("CLARIFY", None, rank(pool), "one scheme matches but the fund house is not named or too little of its name is given", q)
        if len(pool) >= 2:
            return Resolution("CLARIFY", None, rank(pool), f"{len(pool)} schemes match", q)
        top = np.argsort(-sc)[:5]
        return Resolution("CLARIFY", None, rank(top), "no scheme contains all words; closest by character match", q)
