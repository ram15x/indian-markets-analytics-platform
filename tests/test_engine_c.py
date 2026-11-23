"""Engine C (Rust): agrees with A and B, and the engine refuses when any one of the three disagrees."""
import numpy as np
import pytest
from imap import metrics_c
from imap.app import App
from imap.planners import RulePlanner

pytestmark = pytest.mark.skipif(not metrics_c.AVAILABLE, reason="engine C not built (cd engine_c && maturin develop --release)")


@pytest.fixture(scope="module")
def eng():
    return App(RulePlanner()).engine


CASES = [(125497, "cagr", {}), (122639, "max_drawdown", {}), (118955, "volatility", {}),
         (122639, "sip_xirr", dict(amount=5000, day=5)), (125497, "rolling_return", dict(years=3)), (-1, "cagr", {}),
         (-3, "max_drawdown", {})]


@pytest.mark.parametrize("code,metric,extra", CASES)
def test_three_engines_agree(eng, code, metric, extra):
    s = eng.series[code]; end = str(s.dates[-1])
    start = str(s.dates[0]) if metric == "rolling_return" else str(s.dates[-1] - np.timedelta64(3 * 365, "D"))
    r = eng.compute(metric, code, start=start, end=end, **extra)
    assert r.status == "VERIFIED" and r.detail["engines"] == "A+B+C", r.reason


def test_a_wrong_engine_c_is_caught(eng, monkeypatch):
    s = eng.series[125497]; kw = dict(start=str(s.dates[-1] - np.timedelta64(365, "D")), end=str(s.dates[-1]))
    real = eng.c.cagr
    monkeypatch.setattr(eng.c, "cagr", lambda code, **k: dict(real(code, **k), value=real(code, **k)["value"] * (1 + 1e-7)))
    r = eng.compute("cagr", 125497, **kw)
    assert r.status == "WITHHELD" and "C=" in r.reason
    monkeypatch.setattr(eng.c, "max_drawdown", lambda code, **k: dict(eng.b.max_drawdown(code, **k), trough_date="1999-01-01"))
    r = eng.compute("max_drawdown", 125497, **kw)
    assert r.status == "WITHHELD" and "trough_date" in r.reason


def test_bad_input_refused_by_rust():
    with pytest.raises(ValueError):
        metrics_c._c.cagr([1, 1], [1.0, 2.0], 0, 5)              # dates not increasing
    with pytest.raises(ValueError):
        metrics_c._c.cagr([1, 2], [1.0, -2.0], 0, 5)             # negative value
    with pytest.raises(ValueError):
        metrics_c._c.sip_xirr([1, 2], [1.0, 2.0], 5000.0, 0, 5, 40)   # day 40
