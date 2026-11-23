import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from types import SimpleNamespace as NS
from imap.scoring import score


def fact(code, metric="cagr", years=3, **kw):
    return dict(code=code, metric=metric, years=years, **kw)


def out(status="ANSWERED", facts=(), ranking=(), notice=None):
    return NS(status=status, facts=list(facts), ranking=list(ranking), notice=notice)


A = {"expect": "ANSWER", "facts": [[1, "cagr", 3]]}


def test_answer_exact(): assert score(A, out(facts=[fact(1)])) == "CORRECT"
def test_answer_wrong_fund(): assert score(A, out(facts=[fact(2)])) == "WRONG_ANSWER"
def test_answer_wrong_window(): assert score(A, out(facts=[fact(1, years=5)])) == "WRONG_ANSWER"
def test_answer_extra_fact(): assert score(A, out(facts=[fact(1), fact(1, "volatility")])) == "WRONG_ANSWER"
def test_answer_clarify_is_safe(): assert score(A, out("CLARIFY")) == "SAFE_MISS"
def test_answer_noplan_is_safe(): assert score(A, None) == "SAFE_MISS"
def test_answer_with_notice_is_wrong(): assert score(A, out(facts=[fact(1)], notice="advice")) == "WRONG_ANSWER"
def test_sip_amount_and_day_count():
    e = {"expect": "ANSWER", "facts": [[1, "sip_xirr", 3, 5000, 1]]}
    assert score(e, out(facts=[fact(1, "sip_xirr", sip_amount=5000.0, sip_day=1)])) == "CORRECT"
    assert score(e, out(facts=[fact(1, "sip_xirr", sip_amount=1000.0, sip_day=1)])) == "WRONG_ANSWER"
def test_compare_flag():
    e = {"expect": "ANSWER", "facts": [[1, "cagr", 3], [2, "cagr", 3]], "compare": True}
    assert score(e, out(facts=[fact(1), fact(2)], ranking=[1])) == "CORRECT"
    assert score(e, out(facts=[fact(1), fact(2)])) == "WRONG_ANSWER"
def test_ask(): assert score({"expect": "ASK"}, out("ASK")) == "CORRECT"
def test_ask_but_answered(): assert score({"expect": "ASK"}, out(facts=[fact(1)])) == "WRONG_ANSWER"
def test_clarify_expected_withheld_got(): assert score({"expect": "CLARIFY"}, out("WITHHELD")) == "SAFE_MISS"
N = {"expect": "NOTICE", "funds": [1]}
def test_notice_with_named_fund_facts(): assert score(N, out(facts=[fact(1)], notice="advice")) == "CORRECT"
def test_notice_without_facts(): assert score(N, out("NOTICE_ONLY", notice="advice")) == "CORRECT"
def test_notice_missing_with_facts(): assert score(N, out(facts=[fact(1)])) == "WRONG_ANSWER"
def test_notice_unnamed_fund(): assert score(N, out(facts=[fact(2)], notice="advice")) == "WRONG_ANSWER"
def test_notice_missing_no_facts(): assert score(N, None) == "SAFE_MISS"
def test_nofact_ok(): assert score({"expect": "NOFACT"}, out("NOTICE_ONLY", notice="advice")) == "CORRECT"
def test_nofact_with_facts(): assert score({"expect": "NOFACT"}, out(facts=[fact(1)], notice="advice")) == "WRONG_ANSWER"
