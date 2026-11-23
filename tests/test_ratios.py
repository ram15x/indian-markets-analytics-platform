"""Sharpe and Sortino: hand calculation, three-engine agreement, and the rules that withhold them (no data files needed)."""
import math
import numpy as np, pandas as pd, pytest
from imap import metrics_a as A, metrics_c
from imap.engine import Engine
from imap.metrics_b import EngineB
from imap.series import Series

EV = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "kind": pd.Series([], dtype=str), "date": pd.to_datetime([])})
ADJ = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "effective_date": pd.to_datetime([]), "factor": pd.Series([], dtype=float)})


def setup(kind="fund", n=600, rf_every=7, rf_start="2019-12-27", seed=5, bdays=True):
    rng = np.random.default_rng(seed)
    d = pd.bdate_range("2020-01-01", periods=n) if bdays else pd.date_range("2020-01-01", periods=n)
    v = 100 * np.cumprod(1 + rng.normal(0.0005, 0.011, n))
    s = Series(1, d.values.astype("datetime64[D]"), v, kind=kind)
    rd = pd.date_range(rf_start, d[-1], freq=f"{rf_every}D")
    rf = pd.DataFrame(dict(date=rd, yield_pct=6.5 + 0.5 * np.sin(np.arange(len(rd)) / 9)))
    c = metrics_c.EngineC({1: s}) if metrics_c.AVAILABLE else None
    e = Engine({1: s}, EngineB(pd.DataFrame(dict(scheme_code=1, date=d, nav=v)), EV, ADJ), c)
    return e, s, rf


def hand(s, rf, start, end):
    """Plain loops, written from the definition, as the reference."""
    dates = [pd.Timestamp(x) for x in s.dates]; ex = []; ys = []
    rows = list(zip(rf.date, rf.yield_pct, strict=True))
    for k in range(1, len(dates)):
        if not (pd.Timestamp(start) <= dates[k - 1] and dates[k] <= pd.Timestamp(end)): continue
        y = [yy for dd, yy in rows if dd <= dates[k - 1]][-1]
        gap = (dates[k] - dates[k - 1]).days
        ex.append(s.nav[k] / s.nav[k - 1] - 1 - y / 100 * gap / 365); ys.append(y)
    n = len(ex); m = sum(ex) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in ex) / (n - 1)); dd = math.sqrt(sum(min(x, 0) ** 2 for x in ex) / n)
    return m / sd * math.sqrt(252), m / dd * math.sqrt(252), n, sum(ys) / n


def test_matches_hand_calculation_and_engines_agree():
    e, s, rf = setup(); e.set_risk_free(rf)
    st, en = "2020-01-01", str(s.dates[-1])
    sh, so, n, ym = hand(s, rf, st, en)
    a, b = e.compute("sharpe", 1, start=st, end=en), e.compute("sortino", 1, start=st, end=en)
    assert a.status == b.status == "VERIFIED", (a.reason, b.reason)
    assert a.value == pytest.approx(sh, rel=1e-10) and b.value == pytest.approx(so, rel=1e-10)
    assert a.detail["n"] == n == len(s.dates) - 1 and a.detail["mean_rf"] == pytest.approx(ym, rel=1e-12)
    assert a.detail["engines"] == ("A+B+C" if metrics_c.AVAILABLE else "A+B")


def test_weekend_gaps_earn_more_risk_free():
    e, s, rf = setup(); e.set_risk_free(rf)
    exc, _, _, _ = A.excess_returns(s, "2020-01-01", str(s.dates[-1]), *e.rf)
    gaps = np.diff(s.dates).astype(int)
    assert set(gaps) == {1, 3}                          # business days: Friday to Monday is 3 days
    r = s.nav[1:] / s.nav[:-1] - 1
    implied = r - exc
    assert implied[gaps == 3].mean() == pytest.approx(3 * implied[gaps == 1].mean(), rel=0.05)   # simple accrual: 3 days = 3x


def test_withheld_without_rates_too_short_or_stale():
    e, s, rf = setup()
    r = e.compute("sharpe", 1, start="2020-01-01", end=str(s.dates[-1]))
    assert r.status == "WITHHELD" and "not loaded" in r.reason
    e.set_risk_free(rf)
    r = e.compute("sharpe", 1, start=str(s.dates[-50]), end=str(s.dates[-1]))
    assert r.status == "WITHHELD" and "fewer than 120" in r.reason and r.reason.startswith("cannot compute")
    e2, s2, rf2 = setup(rf_every=35); e2.set_risk_free(rf2)                       # rates five weeks apart
    r = e2.compute("sortino", 1, start="2020-01-01", end=str(s2.dates[-1]))
    assert r.status == "WITHHELD" and "days old" in r.reason and r.reason.startswith("cannot compute")
    e3, s3, rf3 = setup(rf_start="2020-03-01"); e3.set_risk_free(rf3)             # no rate before the window starts
    assert e3.compute("sharpe", 1, start="2020-01-01", end=str(s3.dates[-1])).status == "WITHHELD"
    assert e3.compute("sharpe", 1, start="2020-03-02", end=str(s3.dates[-1])).status == "VERIFIED"


def test_monthly_and_fx_series_are_withheld():
    for kind, word in (("monthly", "monthly averages"), ("daily_fx", "exchange rate")):
        e, s, rf = setup(kind=kind); e.set_risk_free(rf)
        for m in ("sharpe", "sortino"):
            r = e.compute(m, 1, start="2020-01-01", end=str(s.dates[-1]))
            assert r.status == "WITHHELD" and word in r.reason


def test_sortino_undefined_when_never_below_the_rate():
    d = pd.bdate_range("2020-01-01", periods=300); v = 100 * 1.002 ** np.arange(300)
    s = Series(1, d.values.astype("datetime64[D]"), v)
    rf = pd.DataFrame(dict(date=pd.date_range("2019-12-27", d[-1], freq="7D"), yield_pct=1.0))
    e = Engine({1: s}, EngineB(pd.DataFrame(dict(scheme_code=1, date=d, nav=v)), EV, ADJ), metrics_c.EngineC({1: s}) if metrics_c.AVAILABLE else None)
    e.set_risk_free(rf)
    r = e.compute("sortino", 1, start="2020-01-01", end=str(s.dates[-1]))
    assert r.status == "WITHHELD" and "no day fell short" in r.reason


def test_answer_sentence_and_planner():
    from imap.answer import sentence
    t = sentence(dict(fund="X Fund", metric="sharpe", value=0.8312,
                      detail=dict(n=741, mean_rf=6.734, start_date="2023-08-28", end_date="2026-08-28")))
    assert "Sharpe ratio was 0.83" in t and "741 daily returns" in t and "6.73% a year" in t and "%" not in t.split("was")[1][:6]
    from imap.planners import RulePlanner
    p = RulePlanner().plan("sortino ratio of sbi small cap 3 years")
    m = [s for s in p["steps"] if s["op"] == "metric"][0]
    assert m["metric"] == "sortino" and m["years"] == 3
    q = [s for s in p["steps"] if s["op"] == "resolve"][0]["query"]
    assert "ratio" not in q and "sortino" not in q


def test_ranking_prints_ratios_not_percentages():
    from imap.answer import render
    from imap.execute import Outcome
    f = lambda c, v: dict(fund=f"F{c}", code=c, metric="sharpe", value=v, notes=[], detail=dict(n=500, mean_rf=6.0, start_date="2023-01-02", end_date="2026-01-02"))
    o = Outcome("ANSWERED", facts=[f(1, 0.8602), f(2, 0.7398)], ranking=[dict(code=1, fund="F1", value=0.8602), dict(code=2, fund="F2", value=0.7398)])
    t = render(o)
    assert "F1 0.86; F2 0.74." in t and "86.02%" not in t


def test_period_is_capped_at_the_last_published_rate_and_keeps_its_length():
    from imap.execute import _window
    e, s, rf = setup(n=900); e.set_risk_free(rf.iloc[:-30])                     # rates stop ~7 months before the NAVs
    cap = e.rf[0][-1] + np.timedelta64(7, "D")
    st, en = _window(s, 2, cap)
    assert np.datetime64(en) <= cap and (pd.Timestamp(en) - pd.Timestamp(st)).days in (730, 731)
    assert e.compute("sharpe", 1, start=st, end=en).status == "VERIFIED"
    assert e.compute("sharpe", 1, start=st, end=str(s.dates[-1])).status == "WITHHELD"   # uncapped: rate too old


# ---- boundaries and messages found by mutation testing (a mutant that moved these limits went unnoticed) ------------
def _flat(n, rf_every=7, y=6.0, constant=False):
    d = pd.date_range("2020-01-01", periods=n)                                  # every calendar day, so every rate age is hit
    v = np.full(n, 100.0) if constant else 100 * np.cumprod(1 + np.random.default_rng(3).normal(0.0004, 0.01, n))
    s = Series(1, d.values.astype("datetime64[D]"), v)
    rf = pd.DataFrame(dict(date=pd.date_range("2019-12-01", d[-1], freq=f"{rf_every}D"), yield_pct=y))
    e = Engine({1: s}, EngineB(pd.DataFrame(dict(scheme_code=1, date=d, nav=v)), EV, ADJ), metrics_c.EngineC({1: s}) if metrics_c.AVAILABLE else None)
    e.set_risk_free(rf)
    return e, s, rf


def test_exactly_120_returns_is_enough_and_119_is_not():
    for metric in ("sharpe", "sortino"):
        e, s, _ = _flat(121)
        r = e.compute(metric, 1, start=str(s.dates[0]), end=str(s.dates[-1]))
        assert r.status == "VERIFIED" and r.detail["n"] == 120, r.reason
        e, s, _ = _flat(120)
        r = e.compute(metric, 1, start=str(s.dates[0]), end=str(s.dates[-1]))
        assert r.status == "WITHHELD" and "fewer than 120" in r.reason


def test_a_rate_exactly_28_days_old_is_accepted_and_29_is_not():
    # a rate every 29 days is at most 28 days old on the last day it covers; every 30 days reaches 29
    e, s, _ = _flat(300, rf_every=29)
    assert e.compute("sharpe", 1, start=str(s.dates[0]), end=str(s.dates[-1])).status == "VERIFIED"
    e, s, _ = _flat(300, rf_every=30)
    r = e.compute("sharpe", 1, start=str(s.dates[0]), end=str(s.dates[-1]))
    assert r.status == "WITHHELD" and "29 days old" in r.reason


def test_no_variation_means_no_ratio():
    e, s, _ = _flat(200, y=0.0, constant=True)                                    # flat NAV and a 0% rate: every excess return is exactly 0
    a, b = (e.compute(m, 1, start=str(s.dates[0]), end=str(s.dates[-1])) for m in ("sharpe", "sortino"))
    assert a.status == "WITHHELD" and "do not vary" in a.reason
    assert b.status == "WITHHELD" and "no day fell short" in b.reason


def test_each_engine_refuses_with_its_own_clear_message():
    e, s, rf = _flat(200, y=0.0, constant=True)
    d0, d1 = str(s.dates[0]), str(s.dates[-1])
    rfd, rfy = e.rf
    with pytest.raises(ValueError, match="do not vary; Sharpe"): A.sharpe(s, d0, d1, rfd, rfy)
    with pytest.raises(ValueError, match="no day fell short of the risk-free rate; Sortino"): A.sortino(s, d0, d1, rfd, rfy)
    with pytest.raises(ValueError, match="no risk-free rate on or before"): A.excess_returns(s, d0, d1, rfd[-3:], rfy[-3:])
    with pytest.raises(ValueError, match="fewer than 120"): A.excess_returns(s, str(s.dates[-50]), d1, rfd, rfy)
    b = e.b
    with pytest.raises(ValueError, match="do not vary; Sharpe"): b.sharpe(1, d0, d1)
    with pytest.raises(ValueError, match="no day fell short of the risk-free rate; Sortino"): b.sortino(1, d0, d1)
    with pytest.raises(ValueError, match="fewer than 120"): b.sharpe(1, str(s.dates[-50]), d1)
    e2, s2, rf2 = _flat(200)
    e2.b.set_risk_free(rf2[rf2.date >= "2020-02-01"])
    with pytest.raises(ValueError, match="no risk-free rate on or before the start"): e2.b.sharpe(1, str(s2.dates[0]), str(s2.dates[-1]))
    e3, s3, rf3 = _flat(300, rf_every=30)
    with pytest.raises(ValueError, match=r"29 days old \(limit 28\)"): e3.b.sharpe(1, str(s3.dates[0]), str(s3.dates[-1]))
    with pytest.raises(ValueError, match="not loaded"): EngineB(pd.DataFrame(dict(scheme_code=1, date=s.dates, nav=s.nav)), EV, ADJ).sharpe(1, d0, d1)


def test_an_interior_window_uses_only_its_own_days():
    e, s, rf = _flat(400)
    st, en = str(s.dates[50]), str(s.dates[260])
    sh, so, n, ym = hand(s, rf, st, en)
    for m, want in (("sharpe", sh), ("sortino", so)):
        r = e.compute(m, 1, start=st, end=en)
        assert r.status == "VERIFIED" and r.detail["n"] == n == 210 and r.value == pytest.approx(want, rel=1e-10)
        assert (r.detail["start_date"], r.detail["end_date"]) == (st, en)
