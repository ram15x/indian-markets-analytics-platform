import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pytest
from imap.estimate import avg_variance, ewma_vol, trailing_vol, vol_estimate, EstimateError
from imap.series import Series


def test_avg_variance_matches_stepping_the_recursion():
    om, al, be, v1, h = 0.05, 0.08, 0.9, 3.0, 21
    v, tot = v1, 0.0
    for _ in range(h):                       # expected variance obeys E[v_{k+1}] = om + (al + be) E[v_k]
        tot += v; v = om + (al + be) * v
    assert avg_variance(om, al, be, v1, h) == pytest.approx(tot / h, rel=1e-12)


def test_avg_variance_of_a_state_at_the_long_run_level_is_that_level():
    om, al, be = 0.05, 0.08, 0.9; lr = om / (1 - al - be)
    assert avg_variance(om, al, be, lr) == pytest.approx(lr, rel=1e-12)


def test_ewma_and_trailing_of_constant_size_returns():
    r = np.full(300, 0.01)
    assert trailing_vol(r) == pytest.approx(0.01 * np.sqrt(252)); assert ewma_vol(r) == pytest.approx(0.01 * np.sqrt(252), rel=1e-6)


def _series(n, daily_sd, kind="fund", seed=1):
    rng = np.random.default_rng(seed); nav = 100 * np.exp(np.cumsum(rng.normal(0, daily_sd, n)))
    return Series(1, np.datetime64("2015-01-01") + np.arange(n), nav, kind=kind)


def test_refuses_what_the_lab_did_not_test():
    for s, msg in ((_series(100, .01), "at least"), (_series(900, .001), "below 8%"), (_series(900, .01, kind="monthly"), "only provided")):
        with pytest.raises(EstimateError, match=msg):
            vol_estimate(s)


def test_garch_estimate_is_close_to_the_true_volatility_of_iid_returns():
    pytest.importorskip("arch")
    out = vol_estimate(_series(1500, .01))               # iid returns with 1% daily sd, about 15.9% a year
    assert out["status"] == "ESTIMATE" and out["garch"] == pytest.approx(0.01 * np.sqrt(252), rel=0.15)
    assert "not verified" in out["label"].lower()
