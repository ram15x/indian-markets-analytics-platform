"""Metric engine facade: computes every metric twice (A numpy, B DuckDB/Python) and refuses to
return a number when the two disagree. Also reports data notes for the window."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from . import metrics_a as A
from .metrics_b import EngineB
from .series import Series

REL_TOL = 1e-9
ABS_FLOOR = 1e-10   # added after one near-flat fund (volatility 5e-8) failed a purely relative test
ABS_TOL = {"sip_xirr": 1e-8}
METRICS = ("total_return", "cagr", "max_drawdown", "volatility", "sip_xirr", "rolling_return", "sharpe", "sortino")
RF_METRICS = ("sharpe", "sortino")
MONTHLY_WITHHELD = {
    "sharpe": "a Sharpe ratio needs daily prices; this series has only monthly averages",
    "sortino": "a Sortino ratio needs daily prices; this series has only monthly averages",
    "volatility": "volatility needs daily prices; this series has only monthly averages",
    "sip_xirr": "a SIP needs the price on each purchase day; this series has only monthly averages"}
DATE_FIELDS = {"total_return": ("start_date", "end_date"), "cagr": ("start_date", "end_date"),
               "max_drawdown": ("peak_date", "trough_date"), "sharpe": ("start_date", "end_date"), "sortino": ("start_date", "end_date")}
# Every field an answer prints must be produced identically by every engine, not just the headline value.
# (Found by mutation testing, 2026-11-23: SIP invested/final value, NAVs and counts were printed but not compared.)
COMPARE_ALL = {"rolling_return": ("value", "min", "max", "pct_negative", "latest", "n", "first_end", "last_end", "min_end", "max_end"),
               "total_return": ("start_nav", "end_nav"), "cagr": ("start_nav", "end_nav", "days"),
               "volatility": ("n",), "sip_xirr": ("invested", "final_value", "n"),
               "sharpe": ("n", "mean_rf"), "sortino": ("n", "mean_rf")}


@dataclass
class Result:
    status: str                   # VERIFIED | WITHHELD
    metric: str; code: int
    value: float | None = None
    detail: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    reason: str = ""


class Engine:
    def __init__(self, series: dict[int, Series], b: EngineB, c=None):
        self.series = series; self.b = b; self.c = c        # c: EngineC (Rust) when installed
        self.rf: tuple | None = None                        # (dates, yields %) for Sharpe / Sortino

    def set_risk_free(self, rf):
        """rf: DataFrame(date, yield_pct) of RBI 91-day T-bill auctions, already checked (contracts.TBILL)."""
        self.rf = (rf.date.to_numpy(dtype="datetime64[D]"), rf.yield_pct.to_numpy(dtype=float))
        self.b.set_risk_free(rf)
        if self.c is not None:
            self.c.set_risk_free(rf)

    def _notes(self, s: Series, start, end) -> list[str]:
        lo, hi = np.datetime64(start, "D"), np.datetime64(end, "D"); out = []
        ex = sorted(d for d in s.excluded if lo <= d <= hi)
        if ex: out.append(f"{len(ex)} NAV(s) in this window were excluded as suspected bad values: {', '.join(map(str, ex[:3]))}")
        lm = [d for d in s.large_moves if lo <= d <= hi]
        if lm: out.append(f"{len(lm)} flagged large move(s) in this window (may be real market moves)")
        return out

    def _not_allowed(self, s: Series, metric: str, kw) -> str | None:
        """Measures that the data cannot support honestly. Checked before computing."""
        if s.kind == "monthly" and metric in MONTHLY_WITHHELD:
            return MONTHLY_WITHHELD[metric]
        if s.kind == "daily_fx" and metric in RF_METRICS:
            return "a Sharpe or Sortino ratio compares an investment's return with a deposit rate; an exchange rate is not such a return"
        lo = np.datetime64(kw.get("start", s.dates[0]), "D"); hi = np.datetime64(kw.get("end", s.dates[-1]), "D")
        if metric == "rolling_return":       # the first period starts one window before the first period end
            lo = (lo.astype("datetime64[M]") - np.timedelta64(12 * int(kw["years"]), "M")).astype("datetime64[D]") + (lo - lo.astype("datetime64[M]").astype("datetime64[D]"))
        for a, b in s.gaps:
            if lo < b and hi > a:
                return f"the source has no data from {a} to {b}, and this window overlaps that gap"
        return None

    def compute(self, metric: str, code: int, **kw) -> Result:
        assert metric in METRICS, metric
        s = self.series[code]
        why = self._not_allowed(s, metric, kw)
        if why:
            return Result("WITHHELD", metric, code, reason=why)
        if metric in RF_METRICS and self.rf is None:
            return Result("WITHHELD", metric, code, reason="the risk-free rate (RBI 91-day T-bill yields) is not loaded yet")
        akw = dict(kw, rf_dates=self.rf[0], rf_yield=self.rf[1]) if metric in RF_METRICS and self.rf is not None else kw
        runs = [("A", lambda: getattr(A, metric)(s, **akw)), ("B", lambda: getattr(self.b, metric)(code, **kw))]
        if self.c is not None:
            runs.append(("C", lambda: getattr(self.c, metric)(code, **kw)))
        got = []
        for name, f in runs:
            try:
                got.append((name, f()))
            except ValueError as e:
                got.append((name, e))
        errs = [n for n, r in got if isinstance(r, Exception)]
        if errs:
            if len(errs) == len(got):
                return Result("WITHHELD", metric, code, reason=f"cannot compute: {got[0][1]}")
            return Result("WITHHELD", metric, code, reason="implementations disagree on feasibility: " + " ".join(f"{n}={r!r}" for n, r in got))
        ra = got[0][1]
        for name, r in got[1:]:
            for k in COMPARE_ALL.get(metric, ()) + DATE_FIELDS.get(metric, ()):
                x, y = ra[k], r[k]
                same = (str(x) == str(y)) if isinstance(x, str) or isinstance(x, int) else abs(x - y) <= max(ABS_FLOOR, REL_TOL * max(abs(x), abs(y)))
                if not same:
                    return Result("WITHHELD", metric, code, reason=f"implementations disagree on {k}: A={x!r} {name}={y!r}")
            va, vb = ra["value"], r["value"]
            tol = max(ABS_FLOOR, ABS_TOL.get(metric, 0.0), REL_TOL * max(abs(va), abs(vb)))
            if abs(va - vb) > tol:
                return Result("WITHHELD", metric, code, reason=f"implementations disagree: A={va!r} {name}={vb!r}")
        ra = dict(ra, engines="+".join(n for n, _ in got))
        start = kw.get("start"); end = kw.get("end")
        return Result("VERIFIED", metric, code, value=va, detail=ra, notes=list(s.notes) + self._notes(s, start, end))
