"""Plans: the only thing a model may produce. A plan is a small DAG of steps; code runs every step.

The model never writes a result number. It may only write parameters (fund text, metric name,
window years, SIP amount/day), and the validator bounds each of them.
"""
from __future__ import annotations
import re

METRICS = ("total_return", "cagr", "max_drawdown", "volatility", "sip_xirr", "rolling_return", "sharpe", "sortino")
OPS = ("resolve", "metric", "compare", "ask")
NOTICES = ("advice", "prediction")
DEFAULT_SIP_AMOUNT = 5000
MAX_STEPS = 12


class PlanError(ValueError):
    pass


def validate(plan: dict) -> list[dict]:
    """Return the steps if the plan is valid; raise PlanError with a reason otherwise."""
    if not isinstance(plan, dict) or set(plan) - {"steps", "notice"} or not isinstance(plan.get("steps"), list):
        raise PlanError("plan must be {'steps': [...], 'notice'?: ...} and nothing else")
    if "notice" in plan and plan["notice"] not in NOTICES:
        raise PlanError(f"notice must be one of {NOTICES}")
    steps = plan["steps"]
    if not (0 if "notice" in plan else 1) <= len(steps) <= MAX_STEPS:
        raise PlanError(f"plan must have 1..{MAX_STEPS} steps")
    seen: dict[str, str] = {}
    for s in steps:
        if not isinstance(s, dict): raise PlanError("each step must be an object")
        sid, op = s.get("id"), s.get("op")
        if not isinstance(sid, str) or not sid or sid in seen: raise PlanError(f"bad or duplicate step id {sid!r}")
        if op not in OPS: raise PlanError(f"unknown op {op!r}")
        if op == "resolve":
            _only(s, {"id", "op", "query"})
            q = s.get("query")
            if not isinstance(q, str) or not 2 <= len(q) <= 120: raise PlanError("resolve.query must be 2..120 chars")
        elif op == "metric":
            _only(s, {"id", "op", "metric", "fund", "years", "amount", "day"})
            if s.get("metric") not in METRICS: raise PlanError(f"unknown metric {s.get('metric')!r}")
            if seen.get(str(s.get("fund"))) != "resolve": raise PlanError("metric.fund must name an earlier resolve step")
            y = s.get("years")
            if not (y == "inception" or (isinstance(y, int) and not isinstance(y, bool) and 1 <= y <= 20)):
                raise PlanError("metric.years must be an integer 1..20 or 'inception'")
            if s["metric"] == "sip_xirr":
                a, d = s.get("amount", DEFAULT_SIP_AMOUNT), s.get("day", 1)
                if not (isinstance(a, (int, float)) and not isinstance(a, bool) and 100 <= a <= 10_000_000): raise PlanError("sip amount must be 100..10,000,000")
                if not (isinstance(d, int) and not isinstance(d, bool) and 1 <= d <= 28): raise PlanError("sip day must be 1..28")
            elif "amount" in s or "day" in s:
                raise PlanError("amount/day only allowed for sip_xirr")
        elif op == "ask":
            _only(s, {"id", "op", "about", "options"})
            opts = s.get("options")
            if s.get("about") != "metric" or not isinstance(opts, list) or not 2 <= len(opts) <= 5 or any(o not in METRICS for o in opts):
                raise PlanError("ask needs about='metric' and 2..5 metric options")
        elif op == "compare":
            _only(s, {"id", "op", "inputs"})
            ins = s.get("inputs")
            if not isinstance(ins, list) or not 2 <= len(ins) <= 8 or any(seen.get(i) != "metric" for i in ins):
                raise PlanError("compare.inputs must list 2..8 earlier metric steps")
        seen[sid] = op
    return steps


def _only(s: dict, allowed: set):
    extra = set(s) - allowed
    if extra: raise PlanError(f"unexpected fields {sorted(extra)} in step {s.get('id')!r}")


def _nums(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def check_against_question(plan: dict, question: str) -> None:
    """Code guards: parameters the model writes must come from the question (or the stated defaults)."""
    q = question.lower(); nums = _nums(q)
    years_said = [int(m) for m in re.findall(r"(\d{1,2})\s*-?\s*(?:y|yr|yrs|year|years)\b", q)]
    inception_said = bool(re.search(r"inception|since (?:start|launch|the start|it started)|ever", q))
    lakh = [n * 100000 for n in _nums(" ".join(re.findall(r"\d[\d,.]*\s*lakh", q)))]
    for s in plan.get("steps", []):
        if s.get("op") != "metric": continue
        y = s.get("years")
        if years_said:
            if y not in years_said: raise PlanError(f"years={y!r} but the question says {years_said}")
        elif y == "inception":
            if not inception_said: raise PlanError("inception window but the question does not ask for it")
        elif y != 3:
            raise PlanError(f"years={y!r} but the question states no window (default is 3)")
        if s.get("metric") == "sip_xirr":
            if "amount" in s and float(s["amount"]) not in nums + lakh:
                raise PlanError(f"SIP amount {s['amount']} is not in the question")
            d = s.get("day", 1)
            if d != 1 and not re.search(rf"\b{d}(?:st|nd|rd|th)?\b", q):
                raise PlanError(f"SIP day {d} is not in the question")
