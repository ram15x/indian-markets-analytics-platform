"""Implementation B: DuckDB SQL plus plain-Python date arithmetic and bisection.

Written independently of A: it builds the adjusted series itself from raw NAVs, the adjustment table
and the bad-value list, and never imports numpy code from A.
"""
from __future__ import annotations
import bisect, calendar, datetime as dt
import math
import duckdb
import pandas as pd


def xirr_bisect(flows: list[tuple]) -> float:
    """Implementation B of XIRR: plain bisection on (date, amount) flows, actual/365."""
    flows = sorted(flows)
    d0 = flows[0][0]
    def f(r): return sum(c / (1 + r) ** ((d - d0).days / 365.0) for d, c in flows)
    lo, hi = -0.9999, 1000.0
    if f(lo) * f(hi) > 0: raise ValueError("XIRR not bracketed")
    for _ in range(300):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
        if hi - lo < 1e-13: break
    return (lo + hi) / 2


class EngineB:
    def __init__(self, nav: pd.DataFrame, events: pd.DataFrame, adj: pd.DataFrame):
        self.con = duckdb.connect()
        # Off: DuckDB would otherwise read any Python variable whose name matches an unknown table, so a typo in a
        # registered name would silently query a different DataFrame (found by mutation testing, 2026-11-23).
        self.con.execute("SET python_enable_replacements = false")
        self.con.register("raw", nav[["scheme_code", "date", "nav"]])
        a = adj[["scheme_code", "effective_date", "factor"]] if len(adj) else pd.DataFrame(
            {"scheme_code": pd.Series(dtype="int64"), "effective_date": pd.Series(dtype="datetime64[ns]"), "factor": pd.Series(dtype="float64")})
        bad = events[events.kind == "BAD_VALUE"][["scheme_code", "date"]] if len(events) else pd.DataFrame(
            {"scheme_code": pd.Series(dtype="int64"), "date": pd.Series(dtype="datetime64[ns]")})
        self.con.register("adj", a); self.con.register("bad", bad)
        self.con.execute("""
            CREATE TABLE s AS
            SELECT r.scheme_code, CAST(r.date AS DATE) AS date,
                   r.nav * COALESCE((SELECT exp(sum(ln(a.factor))) FROM adj a
                                     WHERE a.scheme_code = r.scheme_code AND r.date < a.effective_date), 1.0) AS nav
            FROM raw r
            WHERE NOT EXISTS (SELECT 1 FROM bad b WHERE b.scheme_code = r.scheme_code AND b.date = r.date)
            ORDER BY r.scheme_code, r.date""")

    def _one(self, q, p):
        r = self.con.execute(q, p).fetchone()
        if r is None:
            raise ValueError("no rows in window")
        return r

    def _rows(self, code):
        return self.con.execute("SELECT date, nav FROM s WHERE scheme_code = ? ORDER BY date", [code]).fetchall()

    def _asof(self, code, day):
        r = self.con.execute("SELECT date, nav FROM s WHERE scheme_code=? AND date<=? ORDER BY date DESC LIMIT 1", [code, day]).fetchone()
        if r is None: raise ValueError(f"no NAV on or before {day} for scheme {code}")
        return r

    def total_return(self, code, start, end):
        (d0, n0), (d1, n1) = self._asof(code, start), self._asof(code, end)
        return dict(value=n1 / n0 - 1, start_date=str(d0), end_date=str(d1), start_nav=n0, end_nav=n1)

    def cagr(self, code, start, end):
        t = self.total_return(code, start, end)
        days = (dt.date.fromisoformat(t["end_date"]) - dt.date.fromisoformat(t["start_date"])).days
        if days <= 0: raise ValueError("window has no elapsed days")
        t["value"] = (1 + t["value"]) ** (365.0 / days) - 1; t["days"] = days
        return t

    def rolling_returns(self, code, years, start=None, end=None):
        q = f"""
        WITH e AS (SELECT date, nav, date - INTERVAL {12 * years} MONTH AS begin FROM s WHERE scheme_code = ?
                   {'AND date >= ?' if start is not None else ''} {'AND date <= ?' if end is not None else ''}),
        f AS (SELECT min(date) AS first FROM s WHERE scheme_code = ?)
        SELECT e.date, e.nav / b.nav - 1 AS ret
        FROM e ASOF JOIN (SELECT date, nav FROM s WHERE scheme_code = ?) b ON e.begin >= b.date, f
        WHERE e.begin >= f.first ORDER BY e.date"""
        p = [code] + ([start] if start is not None else []) + ([end] if end is not None else []) + [code, code]
        return self.con.execute(q, p).fetchall()

    def rolling_return(self, code, start, end, years):
        rows = self.rolling_returns(code, years, start, end)
        if not rows:
            raise ValueError(f"history is shorter than {years} years")
        ann = [(d, (1 + r) ** (1.0 / years) - 1) for d, r in rows]
        vals = sorted(a for _, a in ann); n = len(vals)
        med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        lo = min(ann, key=lambda x: (x[1], x[0])); hi = max(ann, key=lambda x: (x[1], -x[0].toordinal()))
        return dict(value=med, min=lo[1], max=hi[1], pct_negative=sum(a < 0 for _, a in ann) / n, latest=ann[-1][1], n=n,
                    first_end=str(ann[0][0]), last_end=str(ann[-1][0]), min_end=str(lo[0]), max_end=str(hi[0]), years=int(years))

    def max_drawdown(self, code, start, end):
        d0, _ = self._asof(code, start); d1, _ = self._asof(code, end)
        rows = self._one("""
            WITH w AS (SELECT date, nav FROM s WHERE scheme_code=? AND date BETWEEN ? AND ?),
            x AS (SELECT date, nav, max(nav) OVER (ORDER BY date) AS peak FROM w),
            y AS (SELECT date, nav / peak - 1 AS dd FROM x)
            SELECT date, dd FROM y ORDER BY dd ASC, date ASC LIMIT 1""", [code, d0, d1])
        tdate, dd = rows
        pk = self._one("SELECT date FROM s WHERE scheme_code=? AND date BETWEEN ? AND ? "
                       "ORDER BY nav DESC, date ASC LIMIT 1", [code, d0, tdate])[0]
        return dict(value=dd, peak_date=str(pk), trough_date=str(tdate))

    def volatility(self, code, start, end):
        d0, _ = self._asof(code, start); d1, _ = self._asof(code, end)
        r = self._one("""
            WITH w AS (SELECT date, nav FROM s WHERE scheme_code=? AND date BETWEEN ? AND ?),
            l AS (SELECT ln(nav / lag(nav) OVER (ORDER BY date)) AS lr FROM w)
            SELECT stddev_samp(lr) * sqrt(252), count(lr) FROM l""", [code, d0, d1])
        if r[1] < 2: raise ValueError("fewer than 3 NAVs in window")
        return dict(value=r[0], n=r[1])

    def sip_xirr(self, code, amount, start, end, day=1):
        rows = self._rows(code); dates = [r[0] for r in rows]; navs = [r[1] for r in rows]
        start = dt.date.fromisoformat(str(start)); end = dt.date.fromisoformat(str(end))
        picks = []; y, m = start.year, start.month
        while True:
            sched = dt.date(y, m, min(day, calendar.monthrange(y, m)[1]))
            if sched > end: break
            if sched >= start:
                i = bisect.bisect_left(dates, sched)
                if i < len(dates) and dates[i] <= end: picks.append(i)
            m += 1
            if m == 13: y, m = y + 1, 1
        if len(picks) < 2: raise ValueError("fewer than 2 instalments in window")
        j = bisect.bisect_right(dates, end) - 1
        if j < 0: raise ValueError("no NAV on or before end")
        units = sum(amount / navs[i] for i in picks); final = units * navs[j]
        flows = [(dates[i], -amount) for i in picks] + [(dates[j], final)]
        return dict(value=xirr_bisect(flows), invested=amount * len(picks), final_value=final, n=len(picks))


    # ---- Sharpe / Sortino: excess returns built in SQL with an ASOF join to the T-bill table ----------------
    def set_risk_free(self, rf):
        """rf: DataFrame(date, yield_pct), one row per auction."""
        self.con.register("rf", rf[["date", "yield_pct"]])
        self.has_rf = True

    def _excess(self, code, start, end):
        if not getattr(self, "has_rf", False):
            raise ValueError("risk-free rate not loaded")
        d0, _ = self._asof(code, start); d1, _ = self._asof(code, end)
        r = self._one("""
            WITH w AS (SELECT date, nav FROM s WHERE scheme_code=? AND date BETWEEN ? AND ?),
            l AS (SELECT date, nav, lag(nav) OVER (ORDER BY date) AS pn, lag(date) OVER (ORDER BY date) AS pd FROM w),
            j AS (SELECT l.date, l.nav, l.pn, l.pd, rf.date AS rd, rf.yield_pct AS y
                  FROM l ASOF LEFT JOIN rf ON l.pd >= rf.date WHERE l.pn IS NOT NULL),
            e AS (SELECT nav / pn - 1 - y / 100 * date_diff('day', pd, date) / 365.0 AS ex, y, rd, pd FROM j)
            SELECT count(*), count(rd), max(date_diff('day', rd, pd)), avg(ex), stddev_samp(ex),
                   sqrt(avg(pow(least(ex, 0), 2))), avg(y) FROM e""", [code, d0, d1])
        n, have, stale, mean, sd, dd, ym = r
        if n < 120: raise ValueError("fewer than 120 daily returns in window")
        if have < n: raise ValueError("no risk-free rate on or before the start of the window")
        if stale > 28: raise ValueError(f"risk-free rate is {stale} days old (limit 28)")
        return n, mean, sd, dd, ym, str(d0), str(d1)

    def sharpe(self, code, start, end):
        n, mean, sd, _, ym, d0, d1 = self._excess(code, start, end)
        if sd == 0: raise ValueError("excess returns do not vary; Sharpe ratio undefined")
        return dict(value=mean / sd * math.sqrt(252), n=n, mean_rf=ym, start_date=d0, end_date=d1)

    def sortino(self, code, start, end):
        n, mean, _, dd, ym, d0, d1 = self._excess(code, start, end)
        if dd == 0: raise ValueError("no day fell short of the risk-free rate; Sortino ratio undefined")
        return dict(value=mean / dd * math.sqrt(252), n=n, mean_rf=ym, start_date=d0, end_date=d1)
