"""Implementation C: Rust (engine_c/, built with maturin). Written separately from the conventions, so a figure is
shown only when numpy (A), DuckDB SQL (B) and Rust (C) agree. C reads the same prepared series as A (the data
preparation is cross-checked by B, which builds its own series in SQL).

If the compiled module is not installed, the app runs with A and B only and says so (`engines` in each result).
Set IMAP_REQUIRE_C=1 to refuse to start without it.
"""
from __future__ import annotations
import os
import numpy as np
from .series import Series

try:
    import imap_engine_c as _c
    AVAILABLE, VERSION = True, _c.VERSION
except ImportError:                      # not built on this machine
    _c, AVAILABLE, VERSION = None, False, None

if os.environ.get("IMAP_REQUIRE_C") == "1" and not AVAILABLE:
    raise ImportError("IMAP_REQUIRE_C=1 but engine C is not installed: cd engine_c && maturin develop --release")


def _day(x) -> int: return int(np.datetime64(x, "D").astype("int64"))
def _iso(n: int) -> str: return str(np.datetime64(int(n), "D"))


class EngineC:
    def __init__(self, series: dict[int, Series]):
        if not AVAILABLE:
            raise RuntimeError("engine C not installed")
        self.series = series; self._cache: dict[int, tuple] = {}

    def _arr(self, code):
        if code not in self._cache:
            s = self.series[code]; self._cache[code] = (s.dates.astype("int64").tolist(), s.nav.astype(float).tolist())
        return self._cache[code]

    def total_return(self, code, start, end):
        r = _c.total_return(*self._arr(code), _day(start), _day(end))
        return dict(value=r["value"], start_date=_iso(r["start_day"]), end_date=_iso(r["end_day"]),
                    start_nav=r["start_value"], end_nav=r["end_value"])

    def cagr(self, code, start, end):
        r = _c.cagr(*self._arr(code), _day(start), _day(end))
        t = _c.total_return(*self._arr(code), _day(start), _day(end))       # the NAVs printed with a CAGR
        return dict(value=r["value"], start_date=_iso(r["start_day"]), end_date=_iso(r["end_day"]), days=r["days"],
                    start_nav=t["start_value"], end_nav=t["end_value"])

    def max_drawdown(self, code, start, end):
        r = _c.max_drawdown(*self._arr(code), _day(start), _day(end))
        return dict(value=r["value"], peak_date=_iso(r["peak_day"]), trough_date=_iso(r["trough_day"]))

    def volatility(self, code, start, end):
        return dict(_c.volatility(*self._arr(code), _day(start), _day(end)))

    def sip_xirr(self, code, amount, start, end, day=1):
        return dict(_c.sip_xirr(*self._arr(code), float(amount), _day(start), _day(end), int(day)))

    def set_risk_free(self, rf):
        self._rf = (rf.date.to_numpy(dtype="datetime64[D]").astype("int64").tolist(), rf.yield_pct.astype(float).tolist())

    def _ratios(self, code, start, end):
        if not hasattr(self, "_rf"):
            raise ValueError("risk-free rate not loaded")
        return _c.sharpe_sortino(*self._arr(code), *self._rf, _day(start), _day(end))

    def sharpe(self, code, start, end):
        r = self._ratios(code, start, end)
        if r["sharpe"] is None: raise ValueError("excess returns do not vary; Sharpe ratio undefined")
        return dict(value=r["sharpe"], n=r["n"], mean_rf=r["mean_rf"], start_date=_iso(r["start_day"]), end_date=_iso(r["end_day"]))

    def sortino(self, code, start, end):
        r = self._ratios(code, start, end)
        if r["sortino"] is None: raise ValueError("no day fell short of the risk-free rate; Sortino ratio undefined")
        return dict(value=r["sortino"], n=r["n"], mean_rf=r["mean_rf"], start_date=_iso(r["start_day"]), end_date=_iso(r["end_day"]))

    def rolling_return(self, code, start, end, years):
        r = _c.rolling_return(*self._arr(code), _day(start), _day(end), int(years))
        out = {k: r[k] for k in ("value", "min", "max", "pct_negative", "latest", "n")}
        out.update(first_end=_iso(r["first_end_day"]), last_end=_iso(r["last_end_day"]), min_end=_iso(r["min_end_day"]),
                   max_end=_iso(r["max_end_day"]), years=int(years))
        return out
