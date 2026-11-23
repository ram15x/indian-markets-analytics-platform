"""Your mutual fund holdings from a CAMS/KFintech Consolidated Account Statement (CAS), local only.

Parsing is done by the open-source `casparser` (MIT). This module turns its output into cash flows and
computes, per scheme and for the whole portfolio: units held, net invested, value, and XIRR, with XIRR
computed by two separate implementations that must agree. Nothing is written to disk. Investor name, PAN,
email, address and mobile are never copied into the result; folio numbers are masked.

Cash-flow direction comes from the transaction TYPE, not the printed sign, so a sign quirk in a statement
cannot turn a purchase into a redemption. Types we cannot value (gifts, segregation, misc, reversals,
unknown) make that scheme's XIRR WITHHELD with the reason.
"""
from __future__ import annotations
import datetime as dt, io
from dataclasses import dataclass, field
import numpy as np
from ..metrics_a import _xirr_newton
from ..metrics_b import xirr_bisect

BUY = {"PURCHASE", "PURCHASE_SIP", "SWITCH_IN", "SWITCH_IN_MERGER"}
SELL = {"REDEMPTION", "SWITCH_OUT", "SWITCH_OUT_MERGER"}
PAYOUT = {"DIVIDEND_PAYOUT"}
COST = {"STAMP_DUTY_TAX", "STT_TAX", "TDS_TAX"}        # money the investor pays (or does not receive)
NEUTRAL = {"DIVIDEND_REINVEST"}                       # units added, no cash moves
UNVALUED = {"GIFT_IN", "GIFT_OUT", "SEGREGATION", "MISC", "REVERSAL", "UNKNOWN"}
UNIT_TOL = 0.002                                      # units; CAS prints 3 decimals
VALUE_TOL = 1.0                                       # rupees


def _d(x) -> dt.date:
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])


def _f(x) -> float:
    return float(x) if x is not None else 0.0


def xirr_checked(flows: list[tuple]) -> tuple[str, float | None, str]:
    """(status, value, reason). VERIFIED only when both implementations agree within 1e-8."""
    flows = [(d, c) for d, c in flows if abs(c) > 1e-9]
    if len(flows) < 2 or not any(c < 0 for _, c in flows) or not any(c > 0 for _, c in flows):
        return "WITHHELD", None, "needs at least one outflow and one inflow"
    flows.sort(); d0 = flows[0][0]
    days = np.array([(d - d0).days for d, _ in flows], float); cf = np.array([c for _, c in flows])
    if days[-1] < 30:
        return "WITHHELD", None, "less than 30 days between first and last cash flow"
    a: float | ValueError; b: float | ValueError
    try:
        a = _xirr_newton(days, cf)
    except ValueError as e:
        a = e
    try:
        b = xirr_bisect(flows)
    except ValueError as e:
        b = e
    if isinstance(a, Exception) or isinstance(b, Exception):
        return "WITHHELD", None, f"XIRR could not be computed: A={a!r} B={b!r}"
    if abs(a - b) > 1e-8:
        return "WITHHELD", None, f"implementations disagree: A={a} B={b}"
    return "VERIFIED", a, ""


@dataclass
class SchemeResult:
    name: str; amfi: str | None; isin: str | None; folio: str; amc: str
    units_close: float; units_from_txns: float; invested_net: float; value: float | None
    valuation_date: str | None; valuation_nav: float | None
    xirr_status: str; xirr: float | None; checks: list = field(default_factory=list)
    flows: list = field(default_factory=list, repr=False)


def _mask(folio: str) -> str:
    f = str(folio or ""); return ("•" * max(0, len(f) - 4)) + f[-4:]


def analyse(cas: dict) -> dict:
    """cas: casparser output (model or dict). Returns a JSON-friendly summary without personal details."""
    if hasattr(cas, "model_dump"):
        cas = cas.model_dump(mode="json", by_alias=True)
    if str(cas.get("cas_type")) not in ("DETAILED", "CASFileType.DETAILED"):
        raise ValueError("this is a SUMMARY statement; request a DETAILED CAS (with transactions) from CAMS or KFintech")
    out: list[SchemeResult] = []; all_flows: list[tuple] = []
    for folio in cas.get("folios", []):
        for s in folio.get("schemes", []):
            txns = s.get("transactions", []); checks = []; flows = []; units = 0.0; invested = 0.0; unvalued = set()
            for t in txns:
                typ = str(t.get("type", "UNKNOWN")).split(".")[-1]; d = _d(t["date"]); amt = abs(_f(t.get("amount"))); u = _f(t.get("units"))
                if typ in BUY:
                    flows.append((d, -amt)); invested += amt; units += abs(u)
                elif typ in SELL:
                    flows.append((d, +amt)); invested -= amt; units -= abs(u)
                elif typ in PAYOUT:
                    flows.append((d, +amt))
                elif typ in COST:
                    flows.append((d, -amt)); invested += amt if typ == "STAMP_DUTY_TAX" else 0.0
                elif typ in NEUTRAL:
                    units += abs(u)
                else:
                    unvalued.add(typ); units += u
            close = _f(s.get("close")); val = s.get("valuation") or {}
            vnav = _f(val.get("nav")) if val.get("nav") is not None else None
            vval = _f(val.get("value")) if val.get("value") is not None else None
            vdate = str(val.get("date"))[:10] if val.get("date") else None
            if abs(units + _f(s.get("open")) - close) > UNIT_TOL:
                checks.append(f"units from transactions ({units + _f(s.get('open')):.3f}) differ from the closing balance ({close:.3f})")
            if _f(s.get("open")) > UNIT_TOL:
                checks.append(f"statement starts with {_f(s.get('open')):.3f} units bought before its period; their cost is not in the statement, so XIRR is withheld")
                unvalued.add("OPENING_BALANCE")
            if vnav is not None and vval is not None and abs(close * vnav - vval) > max(VALUE_TOL, 1e-4 * vval):
                checks.append(f"closing units x NAV ({close * vnav:,.2f}) differs from the printed value ({vval:,.2f})")
            if unvalued:
                status, x, why = "WITHHELD", None, f"contains transactions that cannot be valued as cash: {sorted(unvalued)}"
            elif any(c.startswith("units from") or c.startswith("closing units") for c in checks):
                status, x, why = "WITHHELD", None, "the statement does not reconcile (see checks)"
            elif vval is None or vdate is None:
                status, x, why = "WITHHELD", None, "no valuation in the statement"
            else:
                status, x, why = xirr_checked(flows + ([(_d(vdate), vval)] if vval > 0 else []))
            if why: checks.append(why)
            out.append(SchemeResult(s.get("scheme", ""), s.get("amfi"), s.get("isin"), _mask(folio.get("folio")), folio.get("amc", ""),
                                    close, units + _f(s.get("open")), invested, vval, vdate, vnav, status, x, checks, flows))
            if status == "VERIFIED" and vval is not None and vdate is not None:
                all_flows += flows + ([(_d(vdate), vval)] if vval > 0 else [])
    held = [r for r in out if r.units_close > UNIT_TOL]
    total_value = sum(r.value or 0 for r in held)
    p_status, p_x, p_why = xirr_checked(all_flows) if all_flows else ("WITHHELD", None, "no scheme had a verified XIRR")
    excluded = [r.name for r in out if r.xirr_status != "VERIFIED"]
    warnings = list(cas.get("parse_warnings") or [])
    return dict(
        statement=dict(source=str(cas.get("file_type")), period=cas.get("statement_period"), parser="casparser"),
        parser_warnings=warnings,
        schemes=[dict(name=r.name, amfi=r.amfi, isin=r.isin, folio=r.folio, amc=r.amc, units=r.units_close, invested_net=r.invested_net,
                      value=r.value, valuation_date=r.valuation_date, valuation_nav=r.valuation_nav, xirr_status=r.xirr_status, xirr=r.xirr,
                      checks=r.checks) for r in out],
        portfolio=dict(value=total_value, schemes_held=len(held), xirr_status=p_status, xirr=p_x,
                       note=(p_why or "") + (f" Schemes left out of the portfolio XIRR: {excluded}." if excluded else "")),
        limits="Values are as printed in the statement on its valuation date (source: CAMS/KFintech), not today's NAV. "
               "XIRR uses every purchase, redemption, payout, stamp duty, STT and TDS line in the statement.")


def read_pdf(data: bytes, password: str) -> dict:
    """Parse PDF bytes in memory with casparser and analyse. The password is used once and not kept."""
    import casparser
    cas = casparser.read_cas_pdf(io.BytesIO(data), password)
    return analyse(cas)
