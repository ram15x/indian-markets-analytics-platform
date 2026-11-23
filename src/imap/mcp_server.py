"""MCP server: lets an AI agent (Claude Desktop, Claude Code, any MCP client) use the verified engine as tools.

The agent does the planning; this code does every calculation. Each figure is computed twice (engine A, numpy;
engine B, DuckDB SQL) and returned only if both agree, otherwise WITHHELD with the reason. The same guards as the
web page apply: plans are validated, and periods and SIP amounts must come from the user's own question.

Read-only: no tool writes files, places orders or reaches the network. Transport: stdio (local process only).
Run:  python mcp_server.py      (from the project folder)
"""
from __future__ import annotations
import json
from functools import lru_cache
from typing import Any
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from .app import App
from .planners import RulePlanner, SYSTEM
from .plan import PlanError, METRICS
from .server import outcome_json
from .explain import GLOSSARY, GLOSSARY_VERSION
from . import execute, macro

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
MAX_CODES = 8

mcp = MCPServer(
    "indian-markets-verified",
    instructions=("Past figures for Indian mutual funds (AMFI NAVs), gold and silver (RBI monthly averages) and USD/INR "
                  "(RBI reference rate). Every number is computed twice by independent code and returned only if both "
                  "agree. Quote figures exactly as returned, with their dates and notes. If a result is WITHHELD or "
                  "needs CLARIFY, tell the user; never estimate a figure yourself. This is not advice and makes no predictions."))


@lru_cache(maxsize=1)
def _app() -> App:
    return App(RulePlanner())          # verifies the data manifest; refuses to start on tampered data


def _clean(d: Any) -> Any:
    """JSON-safe copy (numpy scalars -> Python numbers)."""
    return json.loads(json.dumps(d, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


def _run(plan: dict, question: str | None, picks: dict | None = None) -> dict:
    a = _app()
    try:
        o = execute.run(plan, a.resolver, a.engine, question, picks=picks)
    except PlanError as e:
        return dict(status="REJECTED", reason=str(e))
    d = outcome_json(o, "mcp-client", plan)
    return _clean(d)


@mcp.tool(annotations=READ_ONLY)
def find_fund(query: str) -> dict:
    """Look up a mutual fund (Direct, Growth plans) by name, or the phrases 'gold', 'silver', 'usd inr'.
    Returns RESOLVED with one code, or CLARIFY with up to 5 candidates for the user to choose from."""
    q = query.strip()[:200]
    if not q:
        return dict(status="CLARIFY", why="empty query", candidates=[])
    mc = macro.resolve_macro(q)
    if mc is not None and mc in _app().engine.series:
        return dict(status="RESOLVED", code=mc, name=macro.NAMES[mc], why="gold, silver or USD/INR series (exact phrase)")
    r = _app().resolver.resolve(q)
    out: dict[str, Any] = dict(status=r.status, why=r.why, candidates=[dict(code=c, name=n) for c, n, _ in r.candidates])
    if r.status == "RESOLVED":
        out.update(code=r.code, name=next(n for c, n, _ in r.candidates if c == r.code))
    return out


@mcp.tool(annotations=READ_ONLY)
def compute(metric: str, codes: list[int], years: int | str, sip_amount: float | None = None, sip_day: int | None = None) -> dict:
    """Compute one measure for 1-8 codes from find_fund, over the last `years` (1-20) or "inception".
    metric: total_return | cagr | max_drawdown | volatility | sip_xirr | rolling_return.
    For rolling_return, years is the window length. For sip_xirr, sip_amount is required (the user's own amount);
    sip_day defaults to 1. Two or more codes are also ranked. Returns ANSWERED with facts, or WITHHELD with the reason."""
    if metric not in METRICS:
        return dict(status="REJECTED", reason=f"unknown metric {metric!r}; use one of {list(METRICS)}")
    if not 1 <= len(codes) <= MAX_CODES:
        return dict(status="REJECTED", reason=f"give 1 to {MAX_CODES} codes")
    if metric == "sip_xirr" and sip_amount is None:
        return dict(status="REJECTED", reason="sip_xirr needs sip_amount: ask the user how much they invest each month")
    a = _app(); unknown = [c for c in codes if c not in a.engine.series]
    if unknown:
        return dict(status="REJECTED", reason=f"unknown codes {unknown}; get codes from find_fund")
    steps: list[dict[str, Any]] = []; picks: dict[str, int] = {}; mids: list[str] = []
    for k, c in enumerate(dict.fromkeys(codes), 1):
        steps.append(dict(id=f"f{k}", op="resolve", query=f"code {c}")); picks[f"code {c}"] = c
        m: dict[str, Any] = dict(id=f"m{k}", op="metric", metric=metric, fund=f"f{k}", years=years)
        if metric == "sip_xirr" and sip_amount is not None:
            m.update(amount=float(sip_amount), day=int(sip_day or 1))
        steps.append(m); mids.append(m["id"])
    if len(mids) >= 2:
        steps.append(dict(id="c1", op="compare", inputs=mids))
    return _run({"steps": steps}, None, picks)


@mcp.tool(annotations=READ_ONLY)
def answer_question(question: str, plan: dict) -> dict:
    """Answer the user's question from a plan you write (schema: resource imap://plan-schema). The plan is validated
    against the question: periods and SIP amounts must appear in the user's words. Fund names are resolved here;
    if a name is ambiguous the result is CLARIFY with candidates (then use compute with the chosen code)."""
    if len(question) > 2000:
        return dict(status="REJECTED", reason="question too long")
    return _run(plan, question)


@mcp.resource("imap://plan-schema")
def plan_schema() -> str:
    """The plan format answer_question accepts (same rules the web planner follows)."""
    return SYSTEM


@mcp.resource("imap://glossary")
def glossary() -> str:
    """Fixed definitions of each measure (versioned, reviewed text)."""
    return json.dumps(dict(version=GLOSSARY_VERSION, measures=GLOSSARY), indent=1)


@mcp.resource("imap://data-status")
def data_status() -> str:
    """What data is loaded: date ranges, and the manifest that proves the files were not changed."""
    a = _app(); s = a.engine.series
    funds = [x for c, x in s.items() if c > 0]
    d = dict(funds=len(funds), latest_nav=str(max(x.dates[-1] for x in funds)),
             manifest=dict(written_at=a.manifest.get("written_at"), source=a.manifest.get("source")),
             series={macro.NAMES[c]: dict(first=str(s[c].dates[0]), last=str(s[c].dates[-1])) for c in macro.NAMES if c in s})
    return json.dumps(d, indent=1)


def main():
    mcp.run("stdio")


if __name__ == "__main__":
    main()
