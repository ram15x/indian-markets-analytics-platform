"""Shared-window comparison: funds, gold, silver and USD/INR on one period, every figure checked."""
import pytest
from imap.app import App
from imap.planners import RulePlanner
from imap import common, charts, execute

SBI = "SBI Small Cap Fund - Direct Plan - Growth"


@pytest.fixture(scope="module")
def app(): return App(RulePlanner())


def test_gold_silver_fund_share_one_window_and_chart_matches_figures(app):
    o = common.compare(app.engine, app.resolver, ["gold", "silver", SBI], "total_return", 3)
    assert o.status == "ANSWERED" and len(o.facts) == 3 and not o.skipped
    assert o.window == ("2023-04-01", "2026-04-01")          # gold and silver end in Apr 2026: the shortest series sets the end
    assert all("A+B" in x["detail"]["engines"] for x in o.facts)
    assert [r["value"] for r in o.ranking] == sorted((x["value"] for x in o.facts), reverse=True)
    ch = charts.for_outcome(o, app.engine.series)
    assert ch["kind"] == "indexed" and (ch["start"], ch["end"]) == o.window
    for s in ch["series"]:                                    # each line ends where its verified figure says
        fact = next(x for x in o.facts if x["code"] == s["code"])
        assert s["values"][0] == pytest.approx(100.0) and s["values"][-1] == pytest.approx(100 * (1 + fact["value"]), rel=1e-9)


def test_gold_vs_usdinr_is_answered_here_but_still_withheld_by_the_plain_comparison(app):
    o = common.compare(app.engine, app.resolver, ["gold", "usd/inr"], "cagr", 3)
    assert o.status == "ANSWERED" and len(o.facts) == 2
    plain = {"steps": [dict(id="f1", op="resolve", query="gold"), dict(id="f2", op="resolve", query="usd/inr"),
                       dict(id="m1", op="metric", metric="cagr", fund="f1", years=3), dict(id="m2", op="metric", metric="cagr", fund="f2", years=3),
                       dict(id="c1", op="compare", inputs=["m1", "m2"])]}
    w = execute.run(plain, app.resolver, app.engine, "3 year cagr of gold vs usd/inr")
    assert w.status == "WITHHELD" and "do not line up" in w.reason          # the strict path is unchanged


def test_window_longer_than_the_data_is_withheld_with_reasons(app):
    o = common.compare(app.engine, app.resolver, ["gold", "usd/inr"], "cagr", 10)
    assert o.status == "WITHHELD" and "fewer than two" in o.reason


def test_unsupported_measure_for_one_asset_leaves_it_out_with_the_reason(app):
    o = common.compare(app.engine, app.resolver, ["gold", "usd/inr", SBI], "volatility", 3)
    assert o.status == "ANSWERED" and len(o.facts) == 2
    assert [s["fund"] for s in o.skipped] == [o.skipped[0]["fund"]] and "Gold" in o.skipped[0]["fund"] and "daily prices" in o.skipped[0]["reason"]


def test_ambiguous_name_asks_then_pick_resolves(app):
    o = common.compare(app.engine, app.resolver, ["gold", "small cap"], "total_return", 3)
    assert o.status == "CLARIFY" and o.clarify["query"] == "small cap" and len(o.clarify["candidates"]) > 1
    code = 125497                                             # SBI Small Cap, a long-lived fund with current data
    assert code in {c["code"] for c in o.clarify["candidates"]}
    o2 = common.compare(app.engine, app.resolver, ["gold", "small cap"], "total_return", 3, {"small cap": code})
    assert o2.status == "ANSWERED" and {x["code"] for x in o2.facts} >= {code}


@pytest.mark.parametrize("assets,metric,years", [
    (["gold"], "cagr", 3), (["a", "gold", "silver", "usd/inr"], "cagr", 3), (["gold", "silver"], "sharpe", 3),
    (["gold", "silver"], "cagr", True), (["gold", "silver"], "cagr", 0), (["gold", "silver"], "cagr", 16),
    (["gold", "gold"], "cagr", 3), (["gold", 5], "cagr", 3), ("gold silver", "cagr", 3)])
def test_bad_requests_are_refused(app, assets, metric, years):
    with pytest.raises(common.CommonError):
        common.compare(app.engine, app.resolver, assets, metric, years)
