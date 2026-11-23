"""The agreement gate itself, on small synthetic series (fast; no data files needed)."""
import numpy as np, pandas as pd, pytest
from imap.engine import Engine, REL_TOL, ABS_FLOOR
from imap.metrics_b import EngineB
from imap.series import Series

EV = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "kind": pd.Series([], dtype=str), "date": pd.to_datetime([])})
ADJ = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "effective_date": pd.to_datetime([]), "factor": pd.Series([], dtype=float)})


def make(kind="fund", gaps=(), n=900):
    rng = np.random.default_rng(7); d = pd.date_range("2020-01-01", periods=n, freq="D")
    v = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n))
    s = Series(1, d.values.astype("datetime64[D]"), v, kind=kind, gaps=gaps, notes=("note",))
    return Engine({1: s}, EngineB(pd.DataFrame(dict(scheme_code=1, date=d, nav=v)), EV, ADJ)), s


KW = dict(start="2020-03-01", end="2022-05-01")


@pytest.mark.parametrize("m,extra", [("total_return", {}), ("cagr", {}), ("max_drawdown", {}), ("volatility", {}),
                                     ("sip_xirr", dict(amount=1000.0, day=3)), ("rolling_return", dict(years=1))])
def test_verified_when_engines_agree(m, extra):
    e, _ = make(); r = e.compute(m, 1, **KW, **extra)
    assert r.status == "VERIFIED" and r.detail["engines"] == "A+B" and r.notes[0] == "note"


def test_withheld_on_any_disagreement(monkeypatch):
    e, _ = make(); real = e.b.cagr
    v = real(1, **KW)["value"]
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: dict(real(code, **k), value=v * (1 + 50 * REL_TOL)))
    r = e.compute("cagr", 1, **KW)
    assert r.status == "WITHHELD" and "disagree" in r.reason and "B=" in r.reason
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: dict(real(code, **k), value=v * (1 + REL_TOL / 10)))
    assert e.compute("cagr", 1, **KW).status == "VERIFIED"                    # inside tolerance
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: dict(real(code, **k), end_date="1999-01-01"))
    assert "end_date" in e.compute("cagr", 1, **KW).reason                    # dates must agree too
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: (_ for _ in ()).throw(ValueError("boom")))
    assert "feasibility" in e.compute("cagr", 1, **KW).reason


def test_tiny_values_use_the_absolute_floor(monkeypatch):
    e, _ = make(); real = e.b.total_return
    monkeypatch.setattr(e.b, "total_return", lambda code, **k: dict(real(code, **k), value=real(code, **k)["value"] + ABS_FLOOR * 0.5))
    assert e.compute("total_return", 1, **KW).status == "VERIFIED"
    monkeypatch.setattr(e.b, "total_return", lambda code, **k: dict(real(code, **k), value=real(code, **k)["value"] + ABS_FLOOR * 20))
    assert e.compute("total_return", 1, **KW).status == "WITHHELD"


def test_both_infeasible_is_cannot_compute():
    e, _ = make(); r = e.compute("volatility", 1, start="2020-01-01", end="2020-01-02")
    assert r.status == "WITHHELD" and r.reason.startswith("cannot compute")


def test_monthly_series_rules():
    e, _ = make(kind="monthly")
    assert "monthly averages" in e.compute("volatility", 1, **KW).reason
    assert "monthly averages" in e.compute("sip_xirr", 1, amount=1000.0, day=1, **KW).reason
    assert e.compute("cagr", 1, **KW).status == "VERIFIED"


def test_gap_rules():
    g = (np.datetime64("2021-01-01"), np.datetime64("2021-03-01"))
    e, _ = make(gaps=(g,))
    assert "overlaps that gap" in e.compute("cagr", 1, **KW).reason
    assert e.compute("cagr", 1, start="2021-03-01", end="2022-05-01").status == "VERIFIED"
    assert e.compute("cagr", 1, start="2020-03-01", end="2021-01-01").status == "VERIFIED"        # ends exactly at the gap
    assert "overlaps" in e.compute("rolling_return", 1, start="2021-06-01", end="2022-05-01", years=1).reason   # first period starts in the gap
    assert e.compute("rolling_return", 1, start="2022-03-01", end="2022-05-01", years=1).status == "VERIFIED"
