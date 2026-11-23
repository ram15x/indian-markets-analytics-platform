"""Render an Outcome as text. Every number, date and direction word here is produced by code."""
from __future__ import annotations
import datetime as dt

LABEL = dict(total_return="Total return", cagr="CAGR (annualised)", max_drawdown="Maximum drawdown",
             volatility="Annualised volatility", sip_xirr="SIP XIRR", rolling_return="Rolling returns",
             sharpe="Sharpe ratio", sortino="Sortino ratio")
RATIOS = ("sharpe", "sortino")      # plain numbers, not percentages
WARN = "Past data only. This is a calculation, not advice or a prediction."
NOTICE = {"advice": "I can't tell you whether to buy, sell or hold a fund. Here are past figures for the fund(s) you named, so you can judge for yourself.",
          "prediction": "I can't predict how a fund or the market will do. Here are past figures for the fund(s) you named; the past does not tell you the future."}


def _pct(v): return f"{abs(v) * 100:.2f}%"


def _d(s): return dt.date.fromisoformat(str(s)).strftime("%d %b %Y")


def _inr(x):
    s = f"{x:,.0f}"; n = str(int(round(x)))          # Indian grouping: 12,34,567
    if len(n) > 3:
        head, tail = n[:-3], n[-3:]; parts: list[str] = []
        while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
        s = ",".join(([head] if head else []) + parts) + "," + tail
    return "Rs " + s


def sentence(f) -> str:
    d = f["detail"]; name = f["fund"]; m = f["metric"]; v = f["value"]
    span = (f"from {_d(d['start_date'])} to {_d(d['end_date'])}") if "start_date" in d else None
    if m in ("total_return", "cagr"):
        word = "rose" if v > 0 else "fell" if v < 0 else "did not change"
        lv = f.get("level", "NAV"); end_value = 10000 * d["end_nav"] / d["start_nav"]
        what = f"its {lv} {word} by {_pct(v)} in total" if m == "total_return" else f"its {lv} {word} at an average rate of {_pct(v)} a year (CAGR)"
        if lv != "NAV":       # a price series, not an investment: no 'Rs 10,000 invested' line (costs, GST, spreads not included)
            return f"{name}: {span}, {what} ({lv} {d['start_nav']:,.2f} to {d['end_nav']:,.2f})."
        return (f"{name}: {span}, {what}. Rs 10,000 invested at the start would have been about {_inr(end_value)} at the end "
                f"(NAV {d['start_nav']:.4f} to {d['end_nav']:.4f}).")
    if m == "max_drawdown":
        if v == 0: return f"{name}: no fall from a previous high in this period."
        return f"{name}: the deepest fall from a high was {_pct(v)}, from its peak on {_d(d['peak_date'])} to its low on {_d(d['trough_date'])}."
    if m == "volatility":
        return f"{name}: annualised volatility was {_pct(v)} over the period (based on {d['n']} daily {f.get('level', 'NAV')} changes)."
    if m == "sip_xirr":
        assumed = " (amount assumed; XIRR does not depend on a fixed monthly amount)" if f.get("sip_amount_assumed") else ""
        word = "a gain" if v > 0 else "a loss" if v < 0 else "no gain or loss"
        return (f"{name}: investing {_inr(f['sip_amount'])} on day {f['sip_day']} of each month{assumed}, {d['n']} instalments "
                f"totalling {_inr(d['invested'])}, would have been worth {_inr(d['final_value'])}. That is {word}, an annualised "
                f"return (XIRR) of {'-' if v < 0 else ''}{_pct(v)}.")
    if m == "rolling_return":
        y = d["years"]; sg = lambda x: ("-" if x < 0 else "") + _pct(x)
        return (f"{name}: across all {d['n']} {y}-year periods ending between {_d(d['first_end'])} and {_d(d['last_end'])}, the annualised return "
                f"ranged from {sg(d['min'])} (period ending {_d(d['min_end'])}) to {sg(d['max'])} (ending {_d(d['max_end'])}); the middle value was "
                f"{sg(d['value'])}, and {d['pct_negative'] * 100:.1f}% of periods had a negative return. The latest {y}-year period: {sg(d['latest'])} a year.")
    if m in ("sharpe", "sortino"):
        what = "Sharpe ratio" if m == "sharpe" else "Sortino ratio (counts only the days below the risk-free rate as risk)"
        return (f"{name}: from {_d(d['start_date'])} to {_d(d['end_date'])}, the {what} was {v:.2f}, from {d['n']} daily returns compared with "
                f"the RBI 91-day T-bill yield (averaging {d['mean_rf']:.2f}% a year over the period).")
    raise ValueError(m)


def render(o) -> str:
    head = [NOTICE[o.notice]] if getattr(o, "notice", None) else []
    if o.status == "NOTICE_ONLY":
        return "\n".join(head + ["Name a fund if you'd like its past figures.", WARN])
    if o.status == "ASK":
        opts = ", ".join(LABEL[x] for x in o.ask)
        return "\n".join(head + [f"Which measure do you mean? I can give: {opts}."])
    if o.status == "CLARIFY":
        c = o.clarify; lines = head + [f'I could not pin down "{c["query"]}" to one fund ({c["why"]}). Did you mean:']
        lines += [f"  - {x['name']} (scheme {x['code']})" for x in c["candidates"]]
        return "\n".join(lines)
    if o.status == "WITHHELD":
        return "\n".join(head + [f"Withheld: {o.reason}"])
    out = list(head)
    for f in o.facts:
        out.append(sentence(f)); out += [f"  Note: {n}" for n in f["notes"]]
    if o.ranking:
        ratio = o.facts[0]["metric"] in RATIOS
        fmt = (lambda v: f"{v:.2f}") if ratio else (lambda v: f"{'-' if v < 0 else ''}{_pct(v)}")
        out.append("Ordered from highest to lowest value: " + "; ".join(f"{r['fund']} {fmt(r['value'])}" for r in o.ranking) + ".")
    out.append("Matched: " + "; ".join(f"{f['fund']} ({'RBI series' if f['code'] < 0 else 'scheme ' + str(f['code'])})" for f in o.facts)
               + ". Check these are what you meant.")
    out.append(WARN)
    return "\n".join(out)
