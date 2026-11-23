"""Common-window comparison: put funds, gold, silver and USD/INR over one shared period.

Different sources end on different dates (RBI gold and silver stop months before fund NAVs), so a plain
comparison is withheld. This module trims every asset to the latest date they ALL have, says so, and sends each
figure through the same two-engine agreement gate as a single answer. No model is involved.
An asset that cannot be checked over that window is left out with its reason; fewer than two checked assets
means the whole comparison is withheld."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from .engine import Engine
from .execute import Outcome, COMPARE_DAYS
from .resolve import Resolver
from . import macro, metrics_a as A

METRICS = ("total_return", "cagr", "max_drawdown", "volatility")
MIN_ASSETS, MAX_ASSETS = 2, 3          # the chart palette is validated for three series


class CommonError(ValueError):
    pass


def _resolve(text: str, resolver: Resolver, engine: Engine, picks: dict) -> tuple[int, str, str] | Outcome:
    """-> (code, name, how it was matched), or a CLARIFY outcome."""
    key = text.strip().lower()
    if key in picks and picks[key] in engine.series:
        code = picks[key]
        name = macro.NAMES[code] if code < 0 else next(n for c, n in zip(resolver.codes, resolver.names, strict=True) if int(c) == code)
        return code, name, "you chose it from the list"
    fundish = re.search(r"\b(funds?|etfs?|fofs?|schemes?|mf)\b", key)
    mc = None if fundish else macro.resolve_macro(text)
    if mc is not None and mc in engine.series:
        return mc, macro.NAMES[mc], "gold, silver or USD/INR series (exact phrase)"
    r = resolver.resolve(text)
    if r.status != "RESOLVED":
        return Outcome("CLARIFY", clarify=dict(query=text.strip(), why=r.why,
                       candidates=[dict(code=c, name=n) for c, n, _ in r.candidates]))
    assert r.code is not None                      # RESOLVED always carries a code
    return r.code, next(n for c, n, _ in r.candidates if c == r.code), r.why


def compare(engine: Engine, resolver: Resolver, queries: list, metric: str, years, picks: dict | None = None) -> Outcome:
    if metric not in METRICS:
        raise CommonError(f"measure must be one of {', '.join(METRICS)}")
    if not isinstance(years, int) or isinstance(years, bool) or not 1 <= years <= 15:
        raise CommonError("window must be a whole number of years from 1 to 15")
    if not isinstance(queries, list) or not MIN_ASSETS <= len(queries) <= MAX_ASSETS or \
            any(not isinstance(q, str) or not 2 <= len(q.strip()) <= 120 for q in queries):
        raise CommonError(f"name {MIN_ASSETS} to {MAX_ASSETS} assets (each 2 to 120 characters)")
    picks = {str(k).strip().lower(): int(v) for k, v in (picks or {}).items()}
    assets: list[tuple[int, str, str]] = []
    for q in queries:
        r = _resolve(q, resolver, engine, picks)
        if isinstance(r, Outcome):
            return r
        assets.append(r)
    if len({a[0] for a in assets}) != len(assets):
        raise CommonError("the same asset was named twice")

    ends = {a[0]: engine.series[a[0]].dates[-1] for a in assets}
    limiter = min(assets, key=lambda a: ends[a[0]])
    end = ends[limiter[0]]
    start = np.datetime64((pd.Timestamp(end) - pd.DateOffset(years=years)).date(), "D")
    out = Outcome("ANSWERED"); out.window = (str(start), str(end)); skipped: list[dict] = []
    for code, name, how in assets:
        ser = engine.series[code]
        if start < ser.dates[0]:
            skipped.append(dict(fund=name, reason=f"it has data only from {ser.dates[0]}; the shared window starts {start}")); continue
        i, j = A.asof(ser, start), A.asof(ser, end)
        lag_s, lag_e = int((start - ser.dates[i]).astype(int)), int((end - ser.dates[j]).astype(int))
        if max(lag_s, lag_e) > COMPARE_DAYS:
            skipped.append(dict(fund=name, reason=f"its nearest data point is {max(lag_s, lag_e)} days from the window edge (limit {COMPARE_DAYS})")); continue
        res = engine.compute(metric, code, start=str(start), end=str(end))
        if res.status != "VERIFIED":
            skipped.append(dict(fund=name, reason=res.reason)); continue
        notes = list(res.notes) + [f"Shared window {start} to {end}; it ends where the shortest series ends ({limiter[1]})."]
        out.facts.append(dict(step=f"m{len(out.facts) + 1}", metric=metric, code=code, fund=name, matched_by=how, years=years,
                              value=res.value, detail=res.detail, notes=notes, status=res.status, sip_amount=None, sip_day=None,
                              sip_amount_assumed=False, level=macro.LEVEL.get(code, "NAV")))
    out.skipped = skipped
    if len(out.facts) < MIN_ASSETS:
        why = "; ".join(f"{s['fund']}: {s['reason']}" for s in skipped) or "nothing could be computed"
        return Outcome("WITHHELD", reason=f"fewer than two assets could be checked over the shared window ({start} to {end}). {why}")
    out.ranking = [dict(code=x["code"], fund=x["fund"], value=x["value"]) for x in sorted(out.facts, key=lambda x: -x["value"])]
    return out
