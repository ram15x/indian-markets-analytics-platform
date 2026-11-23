"""Run a validated plan with code only. Every number in the output comes from the engine."""
from __future__ import annotations
from dataclasses import dataclass, field
import re
import numpy as np
import pandas as pd
from .plan import validate, check_against_question, DEFAULT_SIP_AMOUNT
from .engine import Engine
from .resolve import Resolver
from . import macro
from .engine import RF_METRICS

COMPARE_DAYS = 7      # end (or start) dates of compared figures may differ by at most this many days


@dataclass
class Outcome:
    status: str                       # ANSWERED | CLARIFY | WITHHELD | ASK | NOTICE_ONLY
    notice: str | None = None
    ask: list | None = None
    facts: list = field(default_factory=list)      # one dict per metric step, code-produced
    ranking: list = field(default_factory=list)
    clarify: dict | None = None
    reason: str = ""


RF_COVER_DAYS = 7      # the last published weekly T-bill yield is taken to cover the following week only


def _window(series, years, cap=None):
    """cap: latest end date allowed (Sharpe/Sortino: last published T-bill week). The period keeps its length."""
    end = series.dates[-1]
    if cap is not None and end > cap:
        end = series.dates[np.searchsorted(series.dates, cap, side="right") - 1]
    if years == "inception":
        return str(series.dates[0]), str(end)
    start = (pd.Timestamp(end) - pd.DateOffset(years=years)).date()
    return str(start), str(end)


def run(plan: dict, resolver: Resolver, engine: Engine, question: str | None = None, picks: dict | None = None) -> Outcome:
    """picks: {fund text as written in the plan (lowercase): scheme code} chosen by the user after a CLARIFY."""
    picks = {k.strip().lower(): int(v) for k, v in (picks or {}).items()}
    steps = validate(plan)
    if question is not None:
        check_against_question(plan, question)
    notice = plan.get("notice")
    if not steps:
        return Outcome("NOTICE_ONLY", notice=notice)
    funds: dict[str, dict] = {}; results: dict[str, dict] = {}; out = Outcome("ANSWERED", notice=notice)
    for s in steps:
        if s["op"] == "ask":
            return Outcome("ASK", notice=notice, ask=list(s["options"]))
        if s["op"] == "resolve":
            pq = s["query"].strip().lower()
            if pq in picks and picks[pq] in engine.series:
                code = picks[pq]
                name = macro.NAMES[code] if code < 0 else next(n for c, n in zip(resolver.codes, resolver.names, strict=True) if int(c) == code)
                funds[s["id"]] = dict(code=code, name=name, query=s["query"], matched_by="you chose it from the list")
                continue
            # a question that says fund/ETF/FoF is about a fund, even if the plan's text lost that word
            fundish = question is not None and re.search(r"\b(funds?|etfs?|fofs?|schemes?|mf)\b", question.lower())
            mc = None if fundish else macro.resolve_macro(s["query"])
            if mc is not None and mc in engine.series:
                funds[s["id"]] = dict(code=mc, name=macro.NAMES[mc], query=s["query"], matched_by="gold, silver or USD/INR series (exact phrase)")
                continue
            r = resolver.resolve(s["query"])
            if r.status != "RESOLVED":
                return Outcome("CLARIFY", notice=notice, clarify=dict(query=s["query"], why=r.why,
                               candidates=[dict(code=c, name=n) for c, n, _ in r.candidates]))
            name = next(n for c, n, _ in r.candidates if c == r.code)
            funds[s["id"]] = dict(code=r.code, name=name, query=s["query"], matched_by=r.why)
        elif s["op"] == "metric":
            f = funds[s["fund"]]; ser = engine.series[f["code"]]
            if s["metric"] == "rolling_return":
                if s["years"] == "inception":
                    return Outcome("WITHHELD", notice=notice, reason="rolling returns need a window length in years (for example 3)")
                start, end = str(ser.dates[0]), str(ser.dates[-1])
                if ser.gaps:      # only periods that start after the source's last gap; the answer's dates show this
                    g = (ser.gaps[-1][1].astype("datetime64[M]") + np.timedelta64(12 * int(s["years"]), "M")).astype("datetime64[D]")
                    start = str(g + (ser.gaps[-1][1] - ser.gaps[-1][1].astype("datetime64[M]").astype("datetime64[D]")))
            else:
                cap = None
                if s["metric"] in RF_METRICS and engine.rf is not None:
                    cap = engine.rf[0][-1] + np.timedelta64(RF_COVER_DAYS, "D")
                start, end = _window(ser, s["years"], cap)
            if s["metric"] != "rolling_return" and s["years"] != "inception" and np.datetime64(start) < ser.dates[0]:
                return Outcome("WITHHELD", notice=notice, reason=f"{f['name']} has data only from {ser.dates[0]}; a {s['years']}-year window is not available")
            kw: dict = dict(start=start, end=end)
            if s["metric"] == "sip_xirr": kw.update(amount=float(s.get("amount", DEFAULT_SIP_AMOUNT)), day=int(s.get("day", 1)))
            if s["metric"] == "rolling_return": kw.update(years=int(s["years"]))
            res = engine.compute(s["metric"], f["code"], **kw)
            if res.status != "VERIFIED":
                return Outcome("WITHHELD", notice=notice, reason=f"{s['metric']} for {f['name']}: {res.reason}")
            fact = dict(step=s["id"], metric=s["metric"], code=f["code"], fund=f["name"], matched_by=f["matched_by"],
                        years=s["years"], value=res.value, detail=res.detail, notes=res.notes, status=res.status,
                        sip_amount=kw.get("amount"), sip_day=kw.get("day"), sip_amount_assumed=(s["metric"] == "sip_xirr" and "amount" not in s),
                        level=macro.LEVEL.get(f["code"], "NAV"))
            if s["metric"] in RF_METRICS and engine.rf is not None and np.datetime64(end) < ser.dates[-1]:
                fact["notes"] = list(fact["notes"]) + [f"The period ends on {end}, not at the latest NAV ({ser.dates[-1]}): RBI has published "
                                                       f"91-day T-bill yields up to {engine.rf[0][-1]} so far."]
            results[s["id"]] = fact; out.facts.append(fact)
        elif s["op"] == "compare":
            xs = [results[i] for i in s["inputs"]]
            if len({x["metric"] for x in xs}) != 1 or len({str(x["years"]) for x in xs}) != 1:
                return Outcome("WITHHELD", reason="compare needs the same metric and window for every fund")
            ends = [x["detail"].get("end_date", x["detail"].get("last_end")) for x in xs]
            starts = [x["detail"].get("start_date", x["detail"].get("first_end")) for x in xs]
            for label, ds in (("end", ends), ("start", starts)):
                dd = [np.datetime64(str(d)[:10]) for d in ds if d is not None]
                if dd and (max(dd) - min(dd)) > np.timedelta64(COMPARE_DAYS, "D"):
                    return Outcome("WITHHELD", notice=notice, reason=f"the periods do not line up ({label} dates {min(dd)} and {max(dd)}), "
                                   "so ranking them would compare different periods")
            out.ranking = [dict(code=x["code"], fund=x["fund"], value=x["value"]) for x in sorted(xs, key=lambda x: -x["value"])]
    if not out.facts:                     # only resolve steps (e.g. an advice question): nothing computed
        return Outcome("NOTICE_ONLY", notice=notice) if notice else Outcome("WITHHELD", reason="the plan computed nothing")
    return out
