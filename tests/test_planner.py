import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap.plan import validate, PlanError
from imap.planners import RulePlanner
from imap.app import App

OK = {"steps": [{"id": "f1", "op": "resolve", "query": "sbi small cap"},
                {"id": "m1", "op": "metric", "metric": "cagr", "fund": "f1", "years": 3}]}


def test_valid_plan_passes():
    assert len(validate(OK)) == 2


@pytest.mark.parametrize("bad", [
    {"steps": []},
    {"steps": OK["steps"], "answer": "CAGR is 25%"},                                   # extra top-level field
    {"steps": [OK["steps"][0], dict(OK["steps"][1], value=0.25)]},                      # model tries to write a number
    {"steps": [OK["steps"][0], dict(OK["steps"][1], metric="alpha")]},                  # unknown metric
    {"steps": [dict(OK["steps"][1])]},                                                  # metric before resolve
    {"steps": [OK["steps"][0], dict(OK["steps"][1], years=50)]},                        # window out of range
    {"steps": [OK["steps"][0], dict(OK["steps"][1], years=True)]},                      # bool is not int
    {"steps": [OK["steps"][0], dict(OK["steps"][1], amount=5000)]},                     # amount on non-SIP
    {"steps": [OK["steps"][0], dict(OK["steps"][1], metric="sip_xirr", amount=5)]},     # SIP amount too small
    {"steps": [OK["steps"][0], {"id": "x", "op": "browse", "url": "http://e"}]},        # tool not allowed
    {"steps": [OK["steps"][0], OK["steps"][0]]},                                        # duplicate id
    {"steps": OK["steps"] + [{"id": "c1", "op": "compare", "inputs": ["m1"]}]},         # compare needs 2+
    {"steps": [{"id": f"f{i}", "op": "resolve", "query": "sbi small cap"} for i in range(13)]},
])
def test_invalid_plans_rejected(bad):
    with pytest.raises(PlanError):
        validate(bad)


@pytest.fixture(scope="module")
def app():
    return App(RulePlanner())


def test_end_to_end_answer_has_code_numbers(app):
    txt, plan = app.ask("What is the 3 year CAGR of sbi small cap?")
    assert "scheme 125497" in txt and "CAGR" in txt and "not advice" in txt


def test_compare_two_funds(app):
    txt, plan = app.ask("Compare 5 year cagr of parag parikh flexi cap vs hdfc flexi cap")
    assert "Ordered from highest to lowest" in txt and "122639" in txt and "118955" in txt


def test_ambiguous_fund_asks(app):
    txt, _ = app.ask("3 year return of gold fund")
    assert txt.startswith("I could not pin down")


def test_window_longer_than_history_withheld(app):
    txt, _ = app.ask("10 year cagr of zerodha silver etf fof")
    assert txt.startswith("Withheld")


def test_old_name_resolves_to_renamed_fund(app):
    txt, _ = app.ask("max drawdown of axis bluechip since inception")
    assert "Axis Large Cap Fund" in txt and "peak on" in txt


from imap.plan import check_against_question
from imap.execute import run as run_plan


def _sip(**kw):
    m = {"id": "m1", "op": "metric", "metric": "sip_xirr", "fund": "f1", "years": 3}; m.update(kw)
    return {"steps": [{"id": "f1", "op": "resolve", "query": "sbi small cap"}, m]}


def test_guard_invented_sip_amount_rejected():
    with pytest.raises(PlanError): check_against_question(_sip(amount=1000), "sip xirr of sbi small cap 3 years")


def test_guard_stated_amount_ok():
    check_against_question(_sip(amount=2500), "sip of Rs 2,500 in sbi small cap for 3 years")


def test_guard_lakh_amount_ok():
    check_against_question(_sip(amount=100000), "sip of 1 lakh a month in sbi small cap for 3 years")


def test_guard_invented_day_rejected():
    with pytest.raises(PlanError): check_against_question(_sip(day=5), "sip xirr of sbi small cap 3 years")


def test_guard_years_must_match_question():
    p = {"steps": [OK["steps"][0], dict(OK["steps"][1], years=5)]}
    with pytest.raises(PlanError): check_against_question(p, "3 year cagr of sbi small cap")
    with pytest.raises(PlanError): check_against_question(p, "cagr of sbi small cap")     # default must be 3
    check_against_question(OK, "cagr of sbi small cap")


def test_guard_inception_needs_words():
    p = {"steps": [OK["steps"][0], dict(OK["steps"][1], years="inception")]}
    with pytest.raises(PlanError): check_against_question(p, "cagr of sbi small cap")
    check_against_question(p, "cagr of sbi small cap since inception")


def test_ask_and_notice_outcomes(app):
    o = run_plan({"steps": [{"id": "a1", "op": "ask", "about": "metric", "options": ["volatility", "max_drawdown"]}]}, app.resolver, app.engine)
    assert o.status == "ASK"
    o = run_plan({"steps": [], "notice": "advice"}, app.resolver, app.engine)
    assert o.status == "NOTICE_ONLY"
    o = run_plan(dict(OK, notice="prediction"), app.resolver, app.engine)
    assert o.status == "ANSWERED" and o.notice == "prediction"


def test_default_sip_amount_is_labelled(app):
    o = run_plan(_sip(), app.resolver, app.engine, "sip xirr of sbi small cap 3 years")
    from imap.answer import render
    assert "amount assumed" in render(o) and o.facts[0]["sip_amount"] == 5000


def test_resolve_only_plan_with_notice_renders_cleanly(app):
    from imap.answer import render
    o = run_plan({"steps": [{"id": "f1", "op": "resolve", "query": "sbi small cap"}], "notice": "advice"}, app.resolver, app.engine)
    assert o.status == "NOTICE_ONLY" and "Matched: ." not in render(o)
