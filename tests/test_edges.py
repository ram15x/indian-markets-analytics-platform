"""Edge cases found by mutation testing (2026-11-23): each test pins a boundary that a deliberate bug survived."""
import numpy as np, pandas as pd, pytest
from imap import metrics_a as A
from imap.engine import Engine, REL_TOL
from imap.metrics_b import EngineB
from imap.series import Series

EV = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "kind": pd.Series([], dtype=str), "date": pd.to_datetime([])})
ADJ = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "effective_date": pd.to_datetime([]), "factor": pd.Series([], dtype=float)})


def daily(vals, start="2019-01-01", **kw):
    d = pd.date_range(start, periods=len(vals), freq="D"); v = np.asarray(vals, float)
    s = Series(1, d.values.astype("datetime64[D]"), v, **kw)
    return s, EngineB(pd.DataFrame(dict(scheme_code=1, date=d, nav=v)), EV, ADJ)


def by_date(s, day):           # with v[i] = 100 + i the value tells which date was used
    return s.nav[int(np.searchsorted(s.dates, np.datetime64(day)))]


# ---- volatility: the 3-value minimum ---------------------------------------------------------------------------
def test_volatility_needs_exactly_three_values():
    s, b = daily([100, 110, 99])
    lr = np.diff(np.log([100, 110, 99])); want = np.std(lr, ddof=1) * np.sqrt(252)
    assert A.volatility(s, "2019-01-01", "2019-01-03")["value"] == pytest.approx(want, rel=1e-12)
    assert b.volatility(1, "2019-01-01", "2019-01-03")["value"] == pytest.approx(want, rel=1e-12)
    for f in (lambda: A.volatility(s, "2019-01-01", "2019-01-02"), lambda: b.volatility(1, "2019-01-01", "2019-01-02")):
        with pytest.raises(ValueError):
            f()


# ---- drawdown: the peak is the high before the trough, not after ---------------------------------------------
def test_drawdown_peak_is_just_before_trough_and_ignores_later_highs():
    s, b = daily([100, 120, 90, 130, 60, 200])
    for r in (A.max_drawdown(s, "2019-01-01", "2019-01-06"), b.max_drawdown(1, "2019-01-01", "2019-01-06")):
        assert r["value"] == pytest.approx(60 / 130 - 1) and r["peak_date"] == "2019-01-04" and r["trough_date"] == "2019-01-05"


# ---- rolling: month-end clamp, first window, single window, annualisation, zero returns ------------------------
def test_rolling_clamps_to_month_end_and_starts_at_the_first_full_window():
    s, b = daily(100 + np.arange(500))                     # 2019-01-01 .. 2020-05-14 (2020 is a leap year)
    rr = A.rolling_returns(s, 1); ends = rr[:, 0].astype("datetime64[D]")
    assert str(ends[0]) == "2020-01-01"                     # first end whose start (2019-01-01) is in the data
    got = dict(zip(map(str, ends), rr[:, 1], strict=True))
    assert got["2020-02-29"] == pytest.approx(by_date(s, "2020-02-29") / by_date(s, "2019-02-28") - 1)   # clamped
    assert got["2020-03-31"] == pytest.approx(by_date(s, "2020-03-31") / by_date(s, "2019-03-31") - 1)
    assert got["2020-03-01"] == pytest.approx(by_date(s, "2020-03-01") / by_date(s, "2019-03-01") - 1)
    rb = dict((str(d), r) for d, r in b.rolling_returns(1, 1))
    assert rb.keys() == got.keys() and all(rb[k] == pytest.approx(got[k], rel=1e-12) for k in got)
    sub = A.rolling_returns(s, 1, start="2020-02-29", end="2020-03-01")                # both bounds inclusive
    assert list(map(str, sub[:, 0].astype("datetime64[D]"))) == ["2020-02-29", "2020-03-01"]


def test_rolling_one_window_and_multi_year_annualising():
    s, b = daily(100 + np.arange(366))                     # 2019-01-01 .. 2020-01-01: exactly one 1-year window
    r = A.rolling_return(s, str(s.dates[0]), str(s.dates[-1]), 1)
    assert r["n"] == 1 and r["value"] == pytest.approx(465 / 100 - 1)
    s2, b2 = daily(100 * 1.0005 ** np.arange(800))         # 2-year windows: annualised = ratio ** (1/2) - 1
    for r in (A.rolling_return(s2, str(s2.dates[0]), str(s2.dates[-1]), 2), b2.rolling_return(1, str(s2.dates[0]), str(s2.dates[-1]), 2)):
        last = s2.nav[-1] / by_date(s2, str(np.datetime64(str(s2.dates[-1])) - np.timedelta64(731, "D")))
        assert r["latest"] == pytest.approx(last ** 0.5 - 1, rel=1e-12) and r["years"] == 2


def test_flat_returns_are_not_counted_as_negative():
    s, b = daily(np.full(800, 50.0))
    for r in (A.rolling_return(s, str(s.dates[0]), str(s.dates[-1]), 1), b.rolling_return(1, str(s.dates[0]), str(s.dates[-1]), 1)):
        assert r["pct_negative"] == 0.0 and r["value"] == 0.0


# ---- SIP: month-end days, inclusive end, end beyond the data, printed fields -------------------------------------
def test_sip_day_31_buys_on_the_last_day_of_short_months():
    s, _ = daily(100 + np.arange(200), start="2020-01-01")
    picks = [str(s.dates[i[0]]) for i in A.sip_schedule(s, "2020-01-01", "2020-06-30", 31)]
    assert picks == ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30", "2020-05-31", "2020-06-30"]


def test_sip_end_date_is_inclusive_and_may_be_past_the_data():
    s, b = daily(100 + np.arange(60), start="2020-01-01")                    # data ends 2020-02-29
    assert len(A.sip_schedule(s, "2020-01-01", "2020-02-05", 5)) == 2        # 5 Jan and 5 Feb (= end)
    r = A.sip_xirr(s, 1000.0, "2020-01-01", "2020-12-31", 5)                  # later months have no NAV: not bought
    assert r["n"] == 2 and r["invested"] == 2000.0
    rb = b.sip_xirr(1, 1000.0, "2020-01-01", "2020-12-31", 5)
    assert rb["n"] == 2 and rb["invested"] == 2000.0 and rb["final_value"] == pytest.approx(r["final_value"], rel=1e-12)


def test_sip_printed_fields_and_two_instalment_minimum():
    s, b = daily(100 + np.arange(60), start="2020-01-01")
    units = 1000 / by_date(s, "2020-01-05") + 1000 / by_date(s, "2020-02-05"); final = units * s.nav[-1]
    for r in (A.sip_xirr(s, 1000.0, "2020-01-01", "2020-02-29", 5), b.sip_xirr(1, 1000.0, "2020-01-01", "2020-02-29", 5)):
        assert r["n"] == 2 and r["invested"] == 2000.0 and r["final_value"] == pytest.approx(final, rel=1e-12)
    with pytest.raises(ValueError):
        A.sip_xirr(s, 1000.0, "2020-01-01", "2020-01-31", 5)                  # one instalment


# ---- engine gate: every field, every path, notes, the optional third engine ---------------------------------------
def make_engine(**kw):
    rng = np.random.default_rng(3); v = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 900))
    s, b = daily(v, start="2020-01-01", **kw)
    return Engine({1: s}, b), s


KW = dict(start="2020-03-01", end="2022-05-01")


def test_withheld_results_carry_status_metric_and_code(monkeypatch):
    e, _ = make_engine(kind="monthly")
    r = e.compute("volatility", 1, **KW)
    assert (r.status, r.metric, r.code) == ("WITHHELD", "volatility", 1)
    e, _ = make_engine()
    r = e.compute("volatility", 1, start="2020-01-01", end="2020-01-02")
    assert (r.status, r.metric, r.code) == ("WITHHELD", "volatility", 1) and "fewer than 3" in r.reason
    real = e.b.cagr
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: (_ for _ in ()).throw(ValueError("x")))
    r = e.compute("cagr", 1, **KW); assert (r.status, r.metric, r.code) == ("WITHHELD", "cagr", 1)
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: dict(real(code, **k), start_nav=1.0))
    r = e.compute("cagr", 1, **KW); assert (r.status, r.metric, r.code) == ("WITHHELD", "cagr", 1) and "start_nav" in r.reason
    monkeypatch.setattr(e.b, "cagr", lambda code, **k: dict(real(code, **k), value=9.0))
    r = e.compute("cagr", 1, **KW); assert (r.status, r.metric, r.code) == ("WITHHELD", "cagr", 1)


def test_verified_result_is_engine_a_with_full_detail():
    e, s = make_engine()
    r = e.compute("cagr", 1, **KW); a = A.cagr(s, **KW)
    assert (r.status, r.metric, r.code, r.value) == ("VERIFIED", "cagr", 1, a["value"])
    assert r.detail["start_date"] == a["start_date"] and r.detail["end_nav"] == a["end_nav"] and r.detail["engines"] == "A+B"


@pytest.mark.parametrize("metric,field,extra", [("sip_xirr", "final_value", dict(amount=1000.0, day=3)), ("sip_xirr", "invested", dict(amount=1000.0, day=3)),
                                               ("sip_xirr", "n", dict(amount=1000.0, day=3)), ("volatility", "n", {}),
                                               ("total_return", "end_nav", {}), ("rolling_return", "min", dict(years=1)),
                                               ("rolling_return", "max_end", dict(years=1))])
def test_every_printed_field_must_agree(monkeypatch, metric, field, extra):
    e, _ = make_engine(); real = getattr(e.b, metric)
    def bump(x): return x + 1 if isinstance(x, int) else (str(np.datetime64(x) + np.timedelta64(1, 'D')) if isinstance(x, str) else x * (1 + 1e-6))
    monkeypatch.setattr(e.b, metric, lambda code, **k: (lambda d: dict(d, **{field: bump(d[field])}))(real(code, **k)))
    r = e.compute(metric, 1, **KW, **extra)
    assert r.status == "WITHHELD" and field in r.reason


def test_field_tolerance_is_relative(monkeypatch):
    e, _ = make_engine(); real = e.b.rolling_return
    monkeypatch.setattr(e.b, "rolling_return", lambda code, **k: (lambda d: dict(d, min=d["min"] * (1 + REL_TOL / 10)))(real(code, **k)))
    assert e.compute("rolling_return", 1, **KW, years=1).status == "VERIFIED"


def test_xirr_has_its_own_absolute_tolerance(monkeypatch):
    e, _ = make_engine(); real = e.b.sip_xirr
    monkeypatch.setattr(e.b, "sip_xirr", lambda code, **k: (lambda d: dict(d, value=d["value"] + 5e-9))(real(code, **k)))
    assert e.compute("sip_xirr", 1, **KW, amount=1000.0, day=3).status == "VERIFIED"
    monkeypatch.setattr(e.b, "sip_xirr", lambda code, **k: (lambda d: dict(d, value=d["value"] + 5e-8))(real(code, **k)))
    assert e.compute("sip_xirr", 1, **KW, amount=1000.0, day=3).status == "WITHHELD"


def test_large_values_use_relative_tolerance(monkeypatch):
    big, bb = daily(np.geomspace(1, 1e6, 900), start="2020-01-01")         # total return ~ 1e5: relative tolerance matters
    e2 = Engine({1: big}, bb); rv = bb.total_return(1, **KW)["value"]; real2 = bb.total_return
    monkeypatch.setattr(e2.b, "total_return", lambda code, **k: dict(real2(code, **k), value=rv * (1 + REL_TOL / 2)))
    assert rv > 1e4 and e2.compute("total_return", 1, **KW).status == "VERIFIED"
    monkeypatch.setattr(e2.b, "total_return", lambda code, **k: dict(real2(code, **k), value=rv * (1 + REL_TOL * 3)))
    assert e2.compute("total_return", 1, **KW).status == "WITHHELD"


def test_a_third_engine_is_used_when_given():
    e, s = make_engine()
    class FakeC:
        def cagr(self, code, **k): return dict(A.cagr(s, **k), value=A.cagr(s, **k)["value"] * 1.01)
    e3 = Engine(e.series, e.b, FakeC())
    r = e3.compute("cagr", 1, **KW)
    assert r.status == "WITHHELD" and "C=" in r.reason


def test_notes_cover_both_ends_of_the_window():
    lo, hi = np.datetime64("2020-03-01"), np.datetime64("2022-05-01")
    e, _ = make_engine(excluded=frozenset({lo, hi, np.datetime64("2019-01-01")}), large_moves=(lo, hi))
    n = e.compute("cagr", 1, start=str(lo), end=str(hi)).notes
    assert n[0].startswith("2 NAV(s)") and "2020-03-01" in n[0] and "2022-05-01" in n[0]
    assert n[1].startswith("2 flagged large move(s)")
    e, _ = make_engine(excluded=frozenset(np.datetime64("2020-06-01") + np.arange(5)))
    assert "2020-06-01, 2020-06-02, 2020-06-03" in e.compute("cagr", 1, **KW).notes[0] and "2020-06-04" not in e.compute("cagr", 1, **KW).notes[0]


def test_rolling_gap_check_uses_the_exact_day():
    gap = (np.datetime64("2020-01-10"), np.datetime64("2020-03-15"))
    e, _ = make_engine(gaps=(gap,))
    assert e.compute("rolling_return", 1, start="2021-03-14", end="2022-05-01", years=1).status == "WITHHELD"
    assert e.compute("rolling_return", 1, start="2021-03-16", end="2022-05-01", years=1).status == "VERIFIED"


# ---- second round (after the re-run): B's data-quality path, medians, ties, exact boundaries ------------------
def test_b_applies_scale_changes_and_drops_bad_values_like_a():
    """A real-shaped raw series: a 10x face-value change and a one-day bad NAV. B rebuilds the adjusted series in SQL."""
    from imap import dq
    from imap.series import build_all
    rng = np.random.default_rng(11); n = 700
    v = 100 * np.cumprod(1 + rng.normal(0.0004, 0.008, n)); v[400:] /= 10          # unit change on day 400
    v[200] = v[199] * 1.9                                                           # one bad value, reverts next day
    d = pd.date_range("2020-01-01", periods=n, freq="D")
    nav = pd.DataFrame(dict(scheme_code=7, date=d, nav=v))
    ev, ad = dq.run(nav)
    assert set(ev.kind) >= {"SCALE_CHANGE", "BAD_VALUE"} and len(ad) == 1
    s = build_all(nav, ev, ad)[7]; b = EngineB(nav, ev, ad); e = Engine({7: s}, b)
    assert np.datetime64("2020-07-19") not in set(s.dates)                          # day 200 excluded
    rows = b._rows(7)
    assert len(rows) == len(s.dates) and np.allclose([r[1] for r in rows], s.nav, rtol=1e-12)
    for m, kw in (("total_return", {}), ("max_drawdown", {}), ("volatility", {}), ("sip_xirr", dict(amount=1000.0, day=2))):
        r = e.compute(m, 7, start="2020-01-01", end=str(d[-1].date()), **kw)
        assert r.status == "VERIFIED", (m, r.reason)
    raw_tr = v[-1] / v[0] - 1
    assert e.compute("total_return", 7, start="2020-01-01", end=str(d[-1].date())).value == pytest.approx((1 + raw_tr) * 10 - 1, rel=1e-12)


def test_short_history_has_no_rolling_windows():
    s, b = daily(100 + np.arange(300))
    assert A.rolling_returns(s, 1).shape == (0, 2) and b.rolling_returns(1, 1) == []
    for f in (lambda: A.rolling_return(s, str(s.dates[0]), str(s.dates[-1]), 1), lambda: b.rolling_return(1, str(s.dates[0]), str(s.dates[-1]), 1)):
        with pytest.raises(ValueError):
            f()


def test_rolling_median_odd_and_even_counts_in_both_engines():
    for n_days, n_win in ((366, 1), (368, 3), (369, 4)):
        s, b = daily(100 * 1.001 ** np.arange(n_days) * (1 + 0.01 * np.sin(np.arange(n_days))))
        ra = A.rolling_return(s, str(s.dates[0]), str(s.dates[-1]), 1); rb = b.rolling_return(1, str(s.dates[0]), str(s.dates[-1]), 1)
        assert ra["n"] == rb["n"] == n_win
        ann = A.rolling_returns(s, 1)[:, 1]            # 1-year windows: total return = annualised return
        assert ra["value"] == pytest.approx(float(np.median(ann)), rel=1e-12) and rb["value"] == pytest.approx(ra["value"], rel=1e-12)


def test_rolling_ties_pick_the_earliest_period_in_both_engines():
    s, b = daily(np.full(800, 50.0))
    ra = A.rolling_return(s, str(s.dates[0]), str(s.dates[-1]), 1); rb = b.rolling_return(1, str(s.dates[0]), str(s.dates[-1]), 1)
    assert ra["max_end"] == rb["max_end"] == ra["min_end"] == rb["min_end"] == ra["first_end"]


def test_b_sip_end_date_is_inclusive():
    s, b = daily(100 + np.arange(60), start="2020-01-01")
    assert b.sip_xirr(1, 1000.0, "2020-01-01", "2020-02-05", 5)["n"] == 2
    assert A.sip_xirr(s, 1000.0, "2020-01-01", "2020-02-05", 5)["n"] == 2


def test_one_day_cagr_is_allowed_zero_days_is_not():
    s, b = daily([100.0, 100.1, 100.3])
    for f in (lambda st, en: A.cagr(s, st, en), lambda st, en: b.cagr(1, st, en)):
        assert f("2019-01-01", "2019-01-02")["value"] == pytest.approx(1.001 ** 365 - 1)
        with pytest.raises(ValueError):
            f("2019-01-02", "2019-01-02")


def test_zero_values_use_the_absolute_floor(monkeypatch):
    from imap.engine import ABS_FLOOR
    s, b = daily(np.full(400, 10.0)); e = Engine({1: s}, b); real = b.total_return
    monkeypatch.setattr(b, "total_return", lambda code, **k: dict(real(code, **k), value=ABS_FLOOR / 2))
    assert e.compute("total_return", 1, start="2019-01-01", end="2019-12-31").status == "VERIFIED"
    monkeypatch.setattr(b, "total_return", lambda code, **k: dict(real(code, **k), value=ABS_FLOOR * 2))
    assert e.compute("total_return", 1, start="2019-01-01", end="2019-12-31").status == "WITHHELD"


def test_third_engine_gets_the_right_code():
    e, s = make_engine(); seen = []
    class SpyC:
        def cagr(self, code, **k): seen.append(code); return A.cagr(s, **k)
    r = Engine(e.series, e.b, SpyC()).compute("cagr", 1, **KW)
    assert seen == [1] and r.status == "VERIFIED" and r.detail["engines"] == "A+B+C"
