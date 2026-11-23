import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd, pytest
from imap import metrics_a as A
from imap.metrics_b import EngineB
from imap.series import Series

EMPTY_EV = pd.DataFrame({"scheme_code": [], "kind": [], "date": pd.to_datetime([])})
EMPTY_ADJ = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "effective_date": pd.to_datetime([]), "factor": []})


def mk(vals, start="2020-01-01"):
    d = pd.date_range(start, periods=len(vals), freq="D")
    df = pd.DataFrame(dict(scheme_code=1, date=d, nav=np.asarray(vals, float)))
    return df, Series(1, d.values.astype("datetime64[D]"), np.asarray(vals, float))


def test_total_return_and_cagr_known():
    df, s = mk(np.linspace(100, 121, 731))        # +21% over 730 days
    assert A.total_return(s, "2020-01-01", "2021-12-31")["value"] == pytest.approx(0.21)
    assert A.cagr(s, "2020-01-01", "2021-12-31")["value"] == pytest.approx(1.21 ** (365 / 730) - 1)


def test_xirr_one_year_ten_percent():
    # single flow pair: -1000 at t0, +1100 365 days later -> 10%
    days = np.array([0., 365.]); cf = np.array([-1000., 1100.])
    assert A._xirr_newton(days, cf) == pytest.approx(0.10, abs=1e-9)


def test_max_drawdown_known():
    df, s = mk([100, 120, 90, 110, 60, 80])
    r = A.max_drawdown(s, "2020-01-01", "2020-01-06")
    assert r["value"] == pytest.approx(60 / 120 - 1) and r["peak_date"] == "2020-01-02" and r["trough_date"] == "2020-01-05"


def test_a_and_b_agree_on_random_walk():
    rng = np.random.default_rng(1)
    vals = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, 1500))
    df, s = mk(vals); b = EngineB(df, EMPTY_EV, EMPTY_ADJ)
    for fn, args in (("total_return", ("2020-03-01", "2023-06-30")), ("cagr", ("2020-03-01", "2023-06-30")),
                     ("max_drawdown", ("2020-03-01", "2023-06-30")), ("volatility", ("2020-03-01", "2023-06-30"))):
        assert getattr(A, fn)(s, *args)["value"] == pytest.approx(getattr(b, fn)(1, *args)["value"], rel=1e-9)
    assert A.sip_xirr(s, 1000, "2020-02-01", "2023-06-30", 5)["value"] == pytest.approx(
        b.sip_xirr(1, 1000, "2020-02-01", "2023-06-30", 5)["value"], abs=1e-9)
    ra = A.rolling_returns(s, 1); rb = b.rolling_returns(1, 1)
    assert len(ra) == len(rb) and np.allclose(ra[:, 1], [x[1] for x in rb])
