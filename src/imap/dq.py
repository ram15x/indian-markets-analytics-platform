"""Data-quality layer: detect unit changes and bad values, never overwrite raw NAVs.

Output: events table, adjustments table (reason-coded), and an adjusted NAV view.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

CLEAN_K = (2, 5, 10, 20, 25, 50, 100, 1000)
MOVE = 0.10            # |daily move| that makes a row a candidate
K_TOL = 0.06           # tolerance around a clean ratio
BACK_TOL = 0.03        # a single-day glitch: next NAV back at the prior level
RETURN_TOL = 0.04      # a longer excursion: the return jump cancels the entry jump
STABLE = 0.10          # level stability either side of a scale change
MAX_TRANSIENT = 30
STALE_N = 5
GAP_DAYS = 10


def _clean_k(ratio: float) -> tuple[float | None, int | None]:
    """Return (k, direction) if ratio is within K_TOL of k or 1/k; direction +1 up, -1 down."""
    for k in CLEAN_K:
        if abs(ratio / k - 1) <= K_TOL:
            return float(k), 1
        if abs(ratio * k - 1) <= K_TOL:
            return float(k), -1
    return None, None


def detect_scheme(code: int, d: np.ndarray, v: np.ndarray) -> tuple[list[dict], list[dict]]:
    """d: datetime64[D] sorted; v: raw NAV. Returns (events, adjustments)."""
    ev: list[dict] = []; adj: list[dict] = []
    n = len(v)
    if n < 3:
        return ev, adj
    r = np.empty(n); r[0] = 1.0; r[1:] = v[1:] / v[:-1]
    cand = np.where(np.abs(r - 1) > MOVE)[0]
    cand = cand[cand > 0]
    skip_until = -1
    for t in map(int, cand):
        if t <= skip_until:
            continue
        prev = v[t - 1]
        # single-day glitch: next value back at prior level
        if t + 1 < n and abs(v[t + 1] / prev - 1) <= BACK_TOL:
            ev.append(dict(scheme_code=code, date=d[t], kind="BAD_VALUE", ratio=r[t], exclude_rows=1))
            skip_until = t + 1  # the next row's move is the glitch reverting
            continue
        # multi-day excursion that returns
        back = None
        for j in range(2, MAX_TRANSIENT + 1):
            # must come back in ONE jump of the opposite sign; gradual recovery is market volatility
            if (t + j < n and abs(r[t] * r[t + j] - 1) <= RETURN_TOL
                    and abs(r[t + j] - 1) > MOVE and (r[t + j] - 1) * (r[t] - 1) < 0):
                back = j; break
        if back is not None:
            ev.append(dict(scheme_code=code, date=d[t], kind="TRANSIENT_SHIFT", ratio=r[t], exclude_rows=0, span_days=back))
            skip_until = t + back
            continue
        # persistent: clean ratio -> scale change, else large move
        k, direction = _clean_k(r[t])
        lo = v[max(0, t - 5):t]; hi = v[t:min(n, t + 5)]
        stable = (np.all(np.abs(lo / lo[-1] - 1) < STABLE) and np.all(np.abs(hi / hi[0] - 1) < STABLE)) if len(lo) and len(hi) else False
        if k is not None and stable:
            # earlier rows are multiplied by factor so the series is continuous
            factor = k if direction == 1 else 1.0 / k
            ev.append(dict(scheme_code=code, date=d[t], kind="SCALE_CHANGE", ratio=r[t], k=k, direction=direction))
            adj.append(dict(scheme_code=code, effective_date=d[t], factor=factor, reason="SCALE_CHANGE", k=k))
        else:
            ev.append(dict(scheme_code=code, date=d[t], kind="LARGE_MOVE", ratio=r[t]))
    # informational flags
    same = (v[1:] == v[:-1])
    if same.any():
        run = 1; start = 0
        for i in range(1, n):
            if v[i] == v[i - 1]:
                run += 1
            else:
                if run >= STALE_N:
                    ev.append(dict(scheme_code=code, date=d[start], kind="STALE_RUN", run=run))
                run = 1; start = i
        if run >= STALE_N:
            ev.append(dict(scheme_code=code, date=d[start], kind="STALE_RUN", run=run))
    gaps = np.diff(d).astype("timedelta64[D]").astype(int)
    for i in map(int, np.where(gaps > GAP_DAYS)[0]):
        ev.append(dict(scheme_code=code, date=d[i + 1], kind="GAP", gap_days=int(gaps[i])))
    return ev, adj


def run(nav: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """nav: scheme_code, date, nav sorted. Returns (events, adjustments)."""
    E: list[dict] = []; A: list[dict] = []
    for code, g in nav.groupby("scheme_code", sort=False):
        e, a = detect_scheme(int(str(code)), g["date"].to_numpy(dtype="datetime64[D]"), g["nav"].to_numpy(dtype=float))
        E += e; A += a
    cols_a = ["scheme_code", "effective_date", "factor", "reason", "k"]
    ev = pd.DataFrame(E); ad = pd.DataFrame(A, columns=cols_a)
    return ev, ad


def apply(nav: pd.DataFrame, events: pd.DataFrame, adj: pd.DataFrame) -> pd.DataFrame:
    """Return nav with nav_adj. Raw nav untouched. Rows before an effective_date get the factor."""
    out = nav.copy()
    out["factor"] = 1.0
    if len(adj):
        for code, a in adj.groupby("scheme_code"):
            m = np.asarray(out["scheme_code"].to_numpy() == code)
            dates = out.loc[m, "date"].to_numpy()
            f = np.ones(int(m.sum()))
            for _, row in a.iterrows():
                f[dates < np.datetime64(row.effective_date)] *= row.factor
            out.loc[m, "factor"] = f
    out["nav_adj"] = out["nav"] * out["factor"]
    out["excluded"] = False
    if len(events):
        bad = events[events.kind == "BAD_VALUE"][["scheme_code", "date"]]
        key = out.set_index(["scheme_code", "date"]).index
        out["excluded"] = key.isin(pd.MultiIndex.from_frame(bad))
        out.loc[out.excluded, "nav_adj"] = np.nan
    return out
