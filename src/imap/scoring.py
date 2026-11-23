"""Scoring rules for docs/PLANNER_EVAL_V2.md. Kept separate so the rules have their own tests."""
from __future__ import annotations


def fact_key(f) -> tuple:
    k = [f["code"], f["metric"], f["years"]]
    if f["metric"] == "sip_xirr":
        k += [int(f["sip_amount"]), int(f["sip_day"])]
    return tuple(k)


def score(expect: dict, outcome, error: str | None = None) -> str:
    """Return CORRECT | WRONG_ANSWER | SAFE_MISS. outcome is None when planning or the plan check failed."""
    exp = expect["expect"]
    status = outcome.status if outcome is not None else "NOPLAN"
    facts = sorted(fact_key(f) for f in outcome.facts) if outcome is not None and status == "ANSWERED" else []
    notice = getattr(outcome, "notice", None) if outcome is not None else None
    if exp == "ANSWER":
        if status != "ANSWERED":
            return "SAFE_MISS"
        want = sorted(tuple(x) for x in expect["facts"])
        same = facts == want and bool(outcome.ranking) == bool(expect.get("compare")) and notice is None
        return "CORRECT" if same else "WRONG_ANSWER"
    if exp in ("ASK", "CLARIFY", "WITHHELD"):
        if facts: return "WRONG_ANSWER"
        return "CORRECT" if status == exp else "SAFE_MISS"
    if exp == "NOTICE":
        if facts and (notice is None or any(k[0] not in expect["funds"] for k in facts)):
            return "WRONG_ANSWER"
        return "CORRECT" if notice is not None else "SAFE_MISS"
    if exp == "NOFACT":
        return "WRONG_ANSWER" if facts else "CORRECT"
    raise ValueError(exp)
