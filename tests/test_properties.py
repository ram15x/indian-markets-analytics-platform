"""Property-based tests: the two metric implementations must agree on random series, and the plan
validator must reject garbage with PlanError (never crash with another exception)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from hypothesis import given, settings, strategies as st, HealthCheck
from imap import metrics_a as A
from imap.metrics_b import EngineB
from imap.series import Series
from imap.plan import validate, check_against_question, PlanError

EV = pd.DataFrame({"scheme_code": [], "kind": [], "date": pd.to_datetime([])})
ADJ = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "effective_date": pd.to_datetime([]), "factor": []})


@st.composite
def series(draw):
    n = draw(st.integers(400, 1400))
    seed = draw(st.integers(0, 2**31 - 1)); rng = np.random.default_rng(seed)
    vol = draw(st.floats(0.0005, 0.03)); drift = draw(st.floats(-0.001, 0.0015))
    steps = rng.integers(1, 4, n)                               # irregular gaps: weekends, holidays
    dates = pd.Timestamp("2015-01-01") + pd.to_timedelta(np.cumsum(steps), unit="D")
    v = 10 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return pd.DataFrame(dict(scheme_code=1, date=dates, nav=v))


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(df=series(), a=st.floats(0.0, 0.45), b=st.floats(0.55, 1.0), day=st.integers(1, 28))
def test_implementations_agree(df, a, b, day):
    d = df.date; start = str((d.iloc[0] + (d.iloc[-1] - d.iloc[0]) * a).date()); end = str((d.iloc[0] + (d.iloc[-1] - d.iloc[0]) * b).date())
    s = Series(1, d.values.astype("datetime64[D]"), df.nav.values); eb = EngineB(df, EV, ADJ)
    for m in ("total_return", "cagr", "max_drawdown", "volatility"):
        va = getattr(A, m)(s, start, end)["value"]; vb = getattr(eb, m)(1, start, end)["value"]
        assert abs(va - vb) <= max(1e-10, 1e-9 * max(abs(va), abs(vb))), (m, va, vb)
    try:
        xa = A.sip_xirr(s, 5000, start, end, day)["value"]
    except ValueError:
        xa = None
    try:
        xb = eb.sip_xirr(1, 5000, start, end, day)["value"]
    except ValueError:
        xb = None
    assert (xa is None) == (xb is None)
    if xa is not None:
        assert abs(xa - xb) <= 1e-8, (xa, xb)


json_values = st.recursive(st.none() | st.booleans() | st.integers(-10**6, 10**6) | st.floats(allow_nan=True) | st.text(max_size=20),
                           lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4), max_leaves=12)
step = st.fixed_dictionaries({}, optional={"id": json_values | st.sampled_from(["f1", "m1", "c1"]), "op": json_values | st.sampled_from(["resolve", "metric", "compare", "ask"]),
                                           "query": json_values, "metric": json_values | st.sampled_from(["cagr", "sip_xirr"]), "fund": json_values | st.just("f1"),
                                           "years": json_values, "amount": json_values, "day": json_values, "inputs": json_values, "options": json_values, "about": json_values})


@settings(max_examples=400, deadline=None)
@given(plan=st.one_of(json_values, st.fixed_dictionaries({"steps": st.lists(step, max_size=6)}, optional={"notice": json_values})), q=st.text(max_size=60))
def test_validator_never_crashes(plan, q):
    try:
        validate(plan); check_against_question(plan, q)
    except PlanError:
        pass


def test_regression_falling_fund_xirr():
    """Found by the property test on 2026-11-23. With these exact inputs the old Newton-only solver raised
    'did not converge' (checked by hand against the old code); B returns about -38.76%."""
    rng = np.random.default_rng(1); n = int(rng.integers(400, 1400)); vol = rng.uniform(0.0005, 0.03); drift = rng.uniform(-0.001, 0.0015)
    dates = pd.Timestamp("2015-01-01") + pd.to_timedelta(np.cumsum(rng.integers(1, 4, n)), unit="D")
    v = 10 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    df = pd.DataFrame(dict(scheme_code=1, date=dates, nav=v)); s = Series(1, dates.values.astype("datetime64[D]"), v)
    xa = A.sip_xirr(s, 5000, "2015-06-27", "2018-08-23", 10)["value"]
    xb = EngineB(df, EV, ADJ).sip_xirr(1, 5000, "2015-06-27", "2018-08-23", 10)["value"]
    assert abs(xa - (-0.38757675869)) < 1e-9 and abs(xa - xb) <= 1e-8
