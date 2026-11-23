"""Verified screener: rank the funds whose name contains some words by one measure over one window.

Every ranked number goes through Engine.compute, the same two-engine agreement gate as a single answer.
A fund that cannot be checked, has too short a history, or has stopped updating is left out and counted.
Funds are filtered by the words in their NAME (the data has no official category column)."""
from __future__ import annotations
import numpy as np
from .engine import Engine, RF_METRICS
from .execute import _window, COMPARE_DAYS

METRICS = ("cagr", "total_return", "volatility", "max_drawdown", "sharpe", "sortino")
LOWER_IS_BETTER = {"volatility"}
MAX_CANDIDATES = 400
MAX_TOP = 50
MIN_WORD = 2


class ScreenError(ValueError):
    pass


def candidates(codes, names, text: str) -> list[tuple[int, str]]:
    words = [w for w in text.lower().split() if w]
    if not words or any(len(w) < MIN_WORD for w in words):
        raise ScreenError("type at least one word of two letters or more, such as: small cap")
    return [(int(c), n) for c, n in zip(codes, names, strict=True) if int(c) > 0 and all(w in n.lower() for w in words)]


def screen(engine: Engine, codes, names, text: str, metric: str, years: int, top: int = 10) -> dict:
    if metric not in METRICS:
        raise ScreenError(f"metric must be one of {', '.join(METRICS)}")
    if not isinstance(years, int) or isinstance(years, bool) or not 1 <= years <= 15:
        raise ScreenError("window must be a whole number of years from 1 to 15")
    top = max(1, min(int(top), MAX_TOP))
    cands = candidates(codes, names, text)
    if not cands:
        return dict(status="NONE", matched=0, reason=f"no fund name contains: {text}")
    if len(cands) > MAX_CANDIDATES:
        raise ScreenError(f"{len(cands)} funds match; add a word to narrow it to {MAX_CANDIDATES} or fewer")
    latest = max(engine.series[c].dates[-1] for c, _ in cands if c in engine.series)
    cap = engine.rf[0][-1] + np.timedelta64(7, "D") if metric in RF_METRICS and engine.rf is not None else None
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    short = stale = withheld = 0
    for code, name in cands:
        ser = engine.series.get(code)
        if ser is None:
            continue
        if latest - ser.dates[-1] > np.timedelta64(COMPARE_DAYS, "D"):
            stale += 1
            continue
        start, end = _window(ser, years, cap)
        if np.datetime64(start) < ser.dates[0]:
            short += 1
            continue
        res = engine.compute(metric, code, start=start, end=end)
        if res.status != "VERIFIED":
            withheld += 1
            reasons[res.reason] = reasons.get(res.reason, 0) + 1
            continue
        rows.append(dict(code=code, fund=name, value=res.value, start=start, end=end))
    rows.sort(key=lambda r: (r["value"] if metric in LOWER_IS_BETTER else -r["value"], r["fund"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return dict(status="OK", metric=metric, years=years, text=text, matched=len(cands), verified=len(rows), too_short=short,
                not_updated=stale, withheld=withheld, withheld_reasons=reasons, order="lowest first" if metric in LOWER_IS_BETTER else "highest first",
                rows=rows[:top], note="Funds are chosen by the words in their name, not an official category. Past figures only; not advice.")
