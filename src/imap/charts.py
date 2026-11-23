"""Chart data from the same adjusted, bad-value-free series the metric engine uses.

Charts are for looking; the verified figures are the ones in the answer cards. tests/test_charts.py checks
that each chart's end points reproduce the verified figure for the same window.
"""
from __future__ import annotations
import numpy as np
from .series import Series
from . import metrics_a as A
from .execute import _window
from . import macro

SHORT = {macro.GOLD: "Gold (RBI, Mumbai)", macro.SILVER: "Silver (RBI, Mumbai)", macro.USDINR: "USD/INR (RBI)"}   # chart labels only

MAX_POINTS = 1500   # per series; thinning keeps every window's first, last, highest and lowest point


def _thin(d: np.ndarray, v: np.ndarray, keep: frozenset[int] | set[int] = frozenset()) -> list[int]:
    n = len(v)
    if n <= MAX_POINTS:
        return list(range(n))
    idx = {0, n - 1} | set(keep)
    edges = np.linspace(0, n, MAX_POINTS // 2 + 1).astype(int)
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if b > a:
            seg = v[a:b]; idx |= {a + int(np.argmin(seg)), a + int(np.argmax(seg))}
    return sorted(idx)


def _flags(s: Series, lo, hi) -> dict:
    lo, hi = np.datetime64(lo, "D"), np.datetime64(hi, "D")
    return dict(excluded=[str(x) for x in sorted(s.excluded) if lo <= x <= hi],
                large_moves=[str(x) for x in s.large_moves if lo <= x <= hi])


def indexed(series: dict[int, Series], names: dict[int, str], codes: list[int], years) -> dict:
    """Each fund's NAV indexed to 100 at the common window start (one axis for every fund)."""
    wins = [_window(series[c], years) for c in codes]
    start = max(np.datetime64(w[0], "D") for w in wins); end = min(np.datetime64(w[1], "D") for w in wins)
    out = []
    for c in codes:
        s = series[c]; i = A.asof(s, start); j = A.asof(s, end)
        d = s.dates[i:j + 1]; v = s.nav[i:j + 1] / s.nav[i] * 100
        k = _thin(d, v)
        out.append(dict(code=c, name=names[c], dates=[str(d[x]) for x in k], values=[float(v[x]) for x in k], **_flags(s, d[0], d[-1])))
    return dict(kind="indexed", unit="index (start = 100)", start=min(x["dates"][0] for x in out), end=max(x["dates"][-1] for x in out), series=out)


def indexed_window(series: dict[int, Series], names: dict[int, str], codes: list[int], start, end) -> dict:
    """Each asset indexed to 100 at an explicit shared window start (same window as the verified figures)."""
    out = []
    for c in codes:
        s = series[c]; i = A.asof(s, start); j = A.asof(s, end)
        d = s.dates[i:j + 1]; v = s.nav[i:j + 1] / s.nav[i] * 100
        k = _thin(d, v)
        out.append(dict(code=c, name=SHORT.get(c, names[c]), dates=[str(d[x]) for x in k], values=[float(v[x]) for x in k], **_flags(s, d[0], d[-1])))
    return dict(kind="indexed", unit="index (start = 100)", start=str(start), end=str(end), series=out)


def drawdown(s: Series, name: str, years) -> dict:
    st, en = _window(s, years); i, j = A.asof(s, st), A.asof(s, en)
    v = s.nav[i:j + 1]; d = s.dates[i:j + 1]; dd = (v / np.maximum.accumulate(v) - 1) * 100
    t = int(np.argmin(dd)); p = int(np.argmax(v[:t + 1]))
    k = _thin(d, dd, {t, p})
    return dict(kind="drawdown", unit="% below previous high", start=str(d[0]), end=str(d[-1]),
                series=[dict(code=s.code, name=name, dates=[str(d[x]) for x in k], values=[float(dd[x]) for x in k], **_flags(s, d[0], d[-1]))],
                marks=dict(peak=str(d[p]), trough=str(d[t]), trough_value=float(dd[t])))


def sip(s: Series, name: str, years, amount: float, day: int) -> dict:
    st, en = _window(s, years); sch = [x[0] for x in A.sip_schedule(s, st, en, day)]; j = A.asof(s, en)
    if len(sch) < 2:
        raise ValueError("fewer than 2 instalments in window")
    d = s.dates[sch[0]:j + 1]; v = s.nav[sch[0]:j + 1]
    buy = np.zeros(len(d)); buy[np.array(sch) - sch[0]] = amount
    units = np.cumsum(buy / s.nav[sch[0]:j + 1]); value = units * v; invested = np.cumsum(buy)
    k = _thin(d, value, set(np.array(sch) - sch[0]))
    pick = lambda arr: [float(arr[x]) for x in k]
    return dict(kind="sip", unit="Rs", start=str(d[0]), end=str(d[-1]),
                series=[dict(code=s.code, name="Value of the SIP", dates=[str(d[x]) for x in k], values=pick(value), **_flags(s, d[0], d[-1])),
                        dict(code=s.code, name="Amount invested", dates=[str(d[x]) for x in k], values=pick(invested), excluded=[], large_moves=[])])


def rolling(s: Series, name: str, years: int) -> dict:
    rr = A.rolling_returns(s, years)
    d = rr[:, 0].astype("datetime64[D]"); v = ((1 + rr[:, 1]) ** (1.0 / years) - 1) * 100
    k = _thin(d, v)
    return dict(kind="rolling", unit=f"% a year, each {years}-year period, by end date", start=str(d[0]), end=str(d[-1]),
                series=[dict(code=s.code, name=name, dates=[str(d[x]) for x in k], values=[float(v[x]) for x in k], **_flags(s, d[0], d[-1]))])


def for_outcome(o, series: dict[int, Series]) -> dict | None:
    """Pick the chart that fits the answer's measure."""
    if o.status != "ANSWERED" or not o.facts:
        return None
    f0 = o.facts[0]; m = f0["metric"]; names = {f["code"]: f["fund"] for f in o.facts}
    codes = list(dict.fromkeys(f["code"] for f in o.facts))[:3]       # palette is validated for three series
    if getattr(o, "window", None):
        return indexed_window(series, names, codes, o.window[0], o.window[1])
    if m == "max_drawdown" and len(codes) == 1:
        return drawdown(series[codes[0]], names[codes[0]], f0["years"])
    if m == "rolling_return" and len(codes) == 1:
        return rolling(series[codes[0]], names[codes[0]], int(f0["years"]))
    if m == "sip_xirr" and len(codes) == 1:
        return sip(series[codes[0]], names[codes[0]], f0["years"], f0["sip_amount"], f0["sip_day"])
    return indexed(series, names, codes, f0["years"])
