"""MCP server: same verified-or-withheld rule as the web page, read-only tools, and a real stdio round trip."""
import json, re, sys
from pathlib import Path
import anyio
from imap import mcp_server as M

SRC = Path(M.__file__).read_text()


def test_find_fund_resolves_or_asks():
    assert M.find_fund("parag parikh flexi cap")["code"] == 122639
    assert M.find_fund("gold")["code"] == -1
    r = M.find_fund("gold fund")
    assert r["status"] == "CLARIFY" and len(r["candidates"]) >= 2
    assert M.find_fund("   ")["status"] == "CLARIFY"


def test_compute_matches_the_app_and_ranks():
    r = M.compute("cagr", [122639, 118955], 5)
    assert r["status"] == "ANSWERED" and len(r["facts"]) == 2 and len(r["ranking"]) == 2
    a = M._app().engine.compute("cagr", 122639, start=r["facts"][0]["start"], end=r["facts"][0]["end"])
    assert r["facts"][0]["value"] == a.value


def test_refusals():
    assert M.compute("treynor", [122639], 3)["status"] == "REJECTED"
    assert M.compute("cagr", [], 3)["status"] == "REJECTED"
    assert M.compute("cagr", list(range(1, 10)), 3)["status"] == "REJECTED"
    assert M.compute("cagr", [999999999], 3)["status"] == "REJECTED"
    assert "sip_amount" in M.compute("sip_xirr", [122639], 3)["reason"]          # no assumed SIP amount over MCP
    assert M.compute("volatility", [-1], 3)["status"] == "WITHHELD"
    assert "do not line up" in M.compute("cagr", [-1, 122639], 5)["reason"]       # gold ends Apr 2026, funds Nov 2026


def test_answer_question_keeps_the_question_guards():
    plan = {"steps": [{"id": "f1", "op": "resolve", "query": "sbi small cap"},
                      {"id": "m1", "op": "metric", "metric": "cagr", "fund": "f1", "years": 10}]}
    assert M.answer_question("5 year CAGR of sbi small cap", plan)["status"] == "REJECTED"
    plan["steps"][1]["years"] = 5
    r = M.answer_question("5 year CAGR of sbi small cap", plan)
    assert r["status"] == "ANSWERED" and r["facts"][0]["code"] == 125497
    assert M.answer_question("x", {"steps": [{"op": "drop table"}]})["status"] == "REJECTED"


def test_tools_are_read_only_by_construction():
    assert not re.search(r"\b(groww|urllib|requests|socket|subprocess)\b|open\([^)]*['\"][wa]", SRC)
    tools = anyio.run(M.mcp.list_tools)
    assert {t.name for t in tools} == {"find_fund", "compute", "answer_question"}
    assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools)


def test_stdio_round_trip():
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.session import ClientSession
    root = Path(__file__).resolve().parents[1]

    async def go():
        p = StdioServerParameters(command=sys.executable, args=[str(root / "mcp_server.py")], cwd=str(root))
        async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("compute", {"metric": "cagr", "codes": [-1, -2], "years": 5})
            d = res.structured_content or json.loads(res.content[0].text)
            st = json.loads((await s.read_resource("imap://data-status")).contents[0].text)
            return d, st
    d, st = anyio.run(go)
    assert d["status"] == "ANSWERED" and [x["code"] for x in d["ranking"]] == [-2, -1]
    assert st["funds"] == 1772
