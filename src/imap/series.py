"""Prepared series: adjusted NAVs with bad values removed, plus notes about flagged dates."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from . import dq


@dataclass
class Series:
    code: int
    dates: np.ndarray            # datetime64[D], sorted
    nav: np.ndarray              # adjusted NAV
    excluded: frozenset = frozenset()   # dates removed as suspected bad values
    large_moves: tuple = ()      # dates of flagged large moves (information only)
    kind: str = "fund"           # fund | monthly (RBI monthly averages) | daily_fx
    gaps: tuple = ()             # (last_date_before, first_date_after) pairs where the source has no data
    notes: tuple = ()            # notes shown with every answer on this series


def build_all(nav: pd.DataFrame, events: pd.DataFrame, adj: pd.DataFrame) -> dict[int, Series]:
    out = dq.apply(nav, events, adj)
    ex = events[events.kind == "BAD_VALUE"].groupby("scheme_code").date.apply(lambda s: frozenset(s.to_numpy(dtype="datetime64[D]")))
    lm = events[events.kind.isin(["LARGE_MOVE", "TRANSIENT_SHIFT"])].groupby("scheme_code").date.apply(lambda s: tuple(s.to_numpy(dtype="datetime64[D]")))
    res: dict[int, Series] = {}
    for code, g in out.groupby("scheme_code", sort=False):
        k = g[~g.excluded]
        c = int(str(code))
        res[c] = Series(c, k.date.to_numpy(dtype="datetime64[D]"), k.nav_adj.to_numpy(dtype=float),
                                ex.get(code, frozenset()), lm.get(code, ()))
    return res
