"""Implementation A: numpy. Conventions are in CONVENTIONS and shared with implementation B."""
from __future__ import annotations
import numpy as np
from .series import Series

CONVENTIONS = dict(
    asof="last valid NAV on or before the requested date",
    year_days=365.0, trading_days=252,
    vol="sample stdev of ln(NAV_t/NAV_t-1) over consecutive NAV dates, times sqrt(252)",
    sip="amount invested at the first NAV date on/after each scheduled day-of-month; XIRR actual/365",
    risk_free="RBI 91-day T-bill cut-off yield (% a year) of the last auction on or before the previous NAV date, "
              "at most 28 days old; per-period rate y/100 * (days between NAVs) / 365 (simple, as RBI quotes it: actual/365)",
    sharpe="mean / sample stdev of daily excess returns (NAV return minus risk-free), times sqrt(252)",
    sortino="mean daily excess return / sqrt(mean(min(excess, 0) ** 2)), times sqrt(252)",
)
MIN_RETURNS = 120          # about six months of daily NAVs; fewer and the ratio is mostly noise
RF_MAX_STALE = 28          # days; weekly auctions, but some are skipped (longest gap 2015-2026: 22 days)
D = "datetime64[D]"
TRADING_DAYS = 252
assert CONVENTIONS["trading_days"] == TRADING_DAYS


def asof(s: Series, day):
    day = np.datetime64(day, "D")
    i = np.searchsorted(s.dates, day, side="right") - 1
    if i < 0:
        raise ValueError(f"no NAV on or before {day} for scheme {s.code}")
    return int(i)


def total_return(s: Series, start, end) -> dict:
    i, j = asof(s, start), asof(s, end)
    return dict(value=float(s.nav[j] / s.nav[i] - 1), start_date=str(s.dates[i]), end_date=str(s.dates[j]),
                start_nav=float(s.nav[i]), end_nav=float(s.nav[j]))


def cagr(s: Series, start, end) -> dict:
    t = total_return(s, start, end)
    days = (np.datetime64(t["end_date"]) - np.datetime64(t["start_date"])).astype(int)
    if days <= 0:
        raise ValueError("window has no elapsed days")
    t["value"] = float((1 + t["value"]) ** (365.0 / days) - 1); t["days"] = int(days)
    return t


def rolling_returns(s: Series, years: int, start=None, end=None) -> np.ndarray:
    """Return array of (end_date, return) for each NAV date that has data one calendar window earlier."""
    ends = s.dates
    if start is not None: ends = ends[ends >= np.datetime64(start, "D")]
    if end is not None: ends = ends[ends <= np.datetime64(end, "D")]
    ends_m = ends.astype("datetime64[M]"); day_off = ends - ends.astype("datetime64[M]")
    begin = (ends_m - np.timedelta64(12 * years, "M")).astype(D) + day_off   # may overflow month end: clamp below
    # clamp to month end when the day does not exist in the earlier month
    month_end = ((ends_m - np.timedelta64(12 * years, "M")) + np.timedelta64(1, "M")).astype(D) - np.timedelta64(1, "D")
    begin = np.minimum(begin, month_end)
    idx = np.searchsorted(s.dates, begin, side="right") - 1
    ok = idx >= 0
    ok &= s.dates[0] <= begin
    i_end = np.searchsorted(s.dates, ends)
    ret = s.nav[i_end[ok]] / s.nav[idx[ok]] - 1
    return np.column_stack([ends[ok].astype("int64"), ret]) if ok.any() else np.empty((0, 2))


def max_drawdown(s: Series, start, end) -> dict:
    i, j = asof(s, start), asof(s, end)
    v = s.nav[i:j + 1]; peak = np.maximum.accumulate(v); dd = v / peak - 1
    k = int(np.argmin(dd)); p = int(np.argmax(v[:k + 1]))
    return dict(value=float(dd[k]), peak_date=str(s.dates[i + p]), trough_date=str(s.dates[i + k]))


def volatility(s: Series, start, end) -> dict:
    i, j = asof(s, start), asof(s, end)
    v = s.nav[i:j + 1]
    if len(v) < 3:
        raise ValueError("fewer than 3 NAVs in window")
    lr = np.diff(np.log(v))
    return dict(value=float(np.std(lr, ddof=1) * np.sqrt(TRADING_DAYS)), n=int(len(lr)))


def _xirr_newton(days: np.ndarray, cf: np.ndarray) -> float:
    """Newton first (fast); if it fails or leaves the valid range, Brent's method on a bracket (scipy).
    Implementation B uses plain bisection, so the two stay independent."""
    t = days / 365.0
    f = lambda r: float(np.sum(cf / (1 + r) ** t))
    r = 0.1
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for _ in range(100):
            fr = np.sum(cf / (1 + r) ** t); df = np.sum(-cf * t / (1 + r) ** (t + 1))
            if not np.isfinite(fr) or not np.isfinite(df) or df == 0: break
            nr = r - fr / df
            if not np.isfinite(nr) or nr <= -0.9999: break
            if abs(nr - r) < 1e-12 and abs(f(nr)) < 1e-6 * np.sum(np.abs(cf)): return float(nr)
            r = nr
    from scipy.optimize import brentq
    lo, hi = -0.9999, 1000.0
    with np.errstate(over="ignore"):
        if not (np.isfinite(f(lo)) and np.isfinite(f(hi))) or f(lo) * f(hi) > 0:
            raise ValueError("XIRR not bracketed")
        return float(brentq(f, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=500))


def sip_schedule(s: Series, start, end, day: int) -> list[tuple]:
    """First NAV date on/after each scheduled day-of-month within [start, end]."""
    start = np.datetime64(start, "D"); end = np.datetime64(end, "D")
    out = []; m = start.astype("datetime64[M]")
    while True:
        first = m.astype(D); last = ((m + np.timedelta64(1, "M")).astype(D) - np.timedelta64(1, "D"))
        sched = min(first + np.timedelta64(day - 1, "D"), last)
        if sched > end: break
        if sched >= start:
            i = int(np.searchsorted(s.dates, sched, side="left"))
            if i < len(s.dates) and s.dates[i] <= end:
                out.append((i,))
        m = m + np.timedelta64(1, "M")
    return out


def sip_xirr(s: Series, amount: float, start, end, day: int = 1) -> dict:
    sch = sip_schedule(s, start, end, day)
    if len(sch) < 2:
        raise ValueError("fewer than 2 instalments in window")
    idx = np.array([x[0] for x in sch]); j = asof(s, end)
    units = (amount / s.nav[idx]).sum(); final = units * s.nav[j]
    d = np.concatenate([s.dates[idx], [s.dates[j]]]); cf = np.concatenate([np.full(len(idx), -amount), [final]])
    days = (d - d[0]).astype(float)
    return dict(value=_xirr_newton(days, cf), invested=float(amount * len(idx)), final_value=float(final), n=int(len(idx)))


def rolling_return(s: Series, start, end, years: int) -> dict:
    """Every `years`-year window ending between start and end, annualised; summary of their spread."""
    rr = rolling_returns(s, years, start, end)
    if len(rr) == 0:
        raise ValueError(f"history is shorter than {years} years")
    ann = (1 + rr[:, 1]) ** (1.0 / years) - 1
    ends = rr[:, 0].astype("datetime64[D]")
    return dict(value=float(np.median(ann)), min=float(ann.min()), max=float(ann.max()), pct_negative=float((ann < 0).mean()),
                latest=float(ann[-1]), n=int(len(ann)), first_end=str(ends[0]), last_end=str(ends[-1]),
                min_end=str(ends[int(np.argmin(ann))]), max_end=str(ends[int(np.argmax(ann))]), years=int(years))


def excess_returns(s: Series, start, end, rf_dates: np.ndarray, rf_yield: np.ndarray) -> tuple[np.ndarray, float, str, str]:
    """Daily excess returns over the window, and the mean yield used (% a year)."""
    i, j = asof(s, start), asof(s, end)
    if j - i < MIN_RETURNS:
        raise ValueError(f"fewer than {MIN_RETURNS} daily returns in window")
    d, v = s.dates[i:j + 1], s.nav[i:j + 1]
    prev = d[:-1]
    k = np.searchsorted(rf_dates, prev, side="right") - 1
    if (k < 0).any():
        raise ValueError(f"no risk-free rate on or before {prev[k < 0][0]}")
    stale = (prev - rf_dates[k]).astype(int)
    if stale.max() > RF_MAX_STALE:
        raise ValueError(f"risk-free rate is {stale.max()} days old on {prev[stale.argmax()]} (limit {RF_MAX_STALE})")
    y = rf_yield[k]
    gap = np.diff(d).astype(int)
    e = (v[1:] / v[:-1] - 1) - y / 100 * gap / 365.0
    return e, float(y.mean()), str(d[0]), str(d[-1])


def sharpe(s: Series, start, end, rf_dates, rf_yield) -> dict:
    e, ym, d0, d1 = excess_returns(s, start, end, rf_dates, rf_yield)
    sd = float(np.std(e, ddof=1))
    if sd == 0:
        raise ValueError("excess returns do not vary; Sharpe ratio undefined")
    return dict(value=float(e.mean() / sd * np.sqrt(TRADING_DAYS)), n=len(e), mean_rf=ym, start_date=d0, end_date=d1)


def sortino(s: Series, start, end, rf_dates, rf_yield) -> dict:
    e, ym, d0, d1 = excess_returns(s, start, end, rf_dates, rf_yield)
    dd = float(np.sqrt(np.mean(np.minimum(e, 0) ** 2)))
    if dd == 0:
        raise ValueError("no day fell short of the risk-free rate; Sortino ratio undefined")
    return dict(value=float(e.mean() / dd * np.sqrt(TRADING_DAYS)), n=len(e), mean_rf=ym, start_date=d0, end_date=d1)
