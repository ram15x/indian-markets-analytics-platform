"""Chart end points must reproduce the verified figures for the same window."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap.app import App
from imap.planners import RulePlanner
from imap import execute, charts


@pytest.fixture(scope="module")
def app(): return App(RulePlanner())


def run(app, q): return execute.run(app.planner.plan(q), app.resolver, app.engine, q)


def test_indexed_matches_total_return(app):
    o = run(app, "What is the 3 year CAGR of SBI Small Cap?"); c = charts.for_outcome(o, app.engine.series)
    s = c["series"][0]; d = o.facts[0]["detail"]
    assert s["dates"][0] == d["start_date"] and s["dates"][-1] == d["end_date"]
    assert s["values"][-1] / 100 == pytest.approx(d["end_nav"] / d["start_nav"], rel=1e-12)


def test_drawdown_trough_matches_metric(app):
    o = run(app, "max drawdown of axis bluechip since inception"); c = charts.for_outcome(o, app.engine.series)
    f = o.facts[0]
    assert c["kind"] == "drawdown" and c["marks"]["trough"] == f["detail"]["trough_date"] and c["marks"]["peak"] == f["detail"]["peak_date"]
    assert c["marks"]["trough_value"] / 100 == pytest.approx(f["value"], rel=1e-12)
    assert min(c["series"][0]["values"]) == pytest.approx(c["marks"]["trough_value"])      # thinning kept the trough


def test_sip_end_matches_metric(app):
    o = run(app, "SIP of Rs 5000 on the 5th in quant small cap for 5 years, what xirr?"); c = charts.for_outcome(o, app.engine.series)
    d = o.facts[0]["detail"]; val, inv = c["series"]
    assert val["values"][-1] == pytest.approx(d["final_value"], rel=1e-12) and inv["values"][-1] == pytest.approx(d["invested"])


def test_compare_is_one_axis_common_start(app):
    o = run(app, "Compare 5 year cagr of parag parikh flexi cap vs hdfc flexi cap"); c = charts.for_outcome(o, app.engine.series)
    assert c["kind"] == "indexed" and len(c["series"]) == 2 and all(s["values"][0] == 100 for s in c["series"])
    assert all(len(s["dates"]) <= charts.MAX_POINTS + 10 for s in c["series"])


def test_no_chart_for_clarify(app):
    assert charts.for_outcome(run(app, "3 year return of gold fund"), app.engine.series) is None


def test_rolling_answer_chart_and_engine_agree(app):
    q = "3 year rolling returns of sbi small cap"
    o = run(app, q); assert o.status == "ANSWERED", o
    f = o.facts[0]; d = f["detail"]
    assert f["metric"] == "rolling_return" and d["n"] > 1000 and d["min"] <= d["value"] <= d["max"]
    c = charts.for_outcome(o, app.engine.series)
    assert c["kind"] == "rolling" and min(c["series"][0]["values"]) == pytest.approx(d["min"] * 100) and max(c["series"][0]["values"]) == pytest.approx(d["max"] * 100)
    # the latest rolling 3-year value equals the 3-year CAGR for the same end date
    o2 = run(app, "3 year cagr of sbi small cap")
    assert d["latest"] == pytest.approx(o2.facts[0]["value"], abs=5e-4)
