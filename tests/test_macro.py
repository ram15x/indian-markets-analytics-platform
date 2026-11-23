"""Gold, silver and USD/INR: source checks, gap and monthly rules, and A/B agreement on the real RBI files."""
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from imap import macro
from imap.app import App
from imap.planners import RulePlanner
from imap.engine import METRICS

DATA = Path(__file__).resolve().parents[1] / "data"
RAW = DATA / "raw" / "rbi"
need_raw = pytest.mark.skipif(not any(RAW.glob("*.XLSX")), reason="RBI files not downloaded (data/raw is not published)")
need_built = pytest.mark.skipif(not (DATA / "macro" / "metals_monthly.parquet").exists(), reason="run python macro.py first")


@need_raw
def test_real_tables_parse_and_cross_check():
    best, rep = macro.load_metals(RAW)
    assert all(f["ok"] for f in rep["files"]) and len(rep["files"]) == 3
    assert rep["months"] == 109 and rep["first"] == "Apr 2017" and rep["last"] == "Apr 2026" and rep["gaps"] == []
    assert rep.get("average_mismatches", []) == []           # every fiscal-year Average row equals the mean of its months
    # editions agree on every price; they disagree only on Table 163's silver spread (Jul 2024 - Jun 2025)
    assert len(rep["edition_conflicts"]) == 12 and all("silver_spread_inr" in c for c in rep["edition_conflicts"])
    t163 = [e for e in rep["spread_errors"] if e.startswith("Table 163")]
    assert len(t163) == 12 and all("silver spread" in e for e in t163)
    # after newest-edition-wins, the only inconsistency left is the reviewed Rs 10 gold spread in Jul 2019
    assert rep["spread_errors_in_kept_rows"] == ["Table 162 Jul 2019: gold spread 3254.37 != Mumbai - London (3264.37)"]
    assert set(best.table[best.month >= pd.Timestamp("2022-04-01").date()]) == {164}


@need_raw
def test_unreviewed_inconsistency_stops_build_and_keeps_old_data(tmp_path):
    shutil.copytree(RAW, tmp_path / "raw" / "rbi")           # no macro_notes.csv here, so Jul 2019 is unreviewed
    rep = macro.build(tmp_path)
    assert rep["ok"] is False and rep["metals"]["unreviewed_in_kept_rows"]
    assert not (tmp_path / "macro" / "metals_monthly.parquet").exists() and (tmp_path / "macro" / "report_failed.json").exists()
    shutil.copy(DATA / "macro_notes.csv", tmp_path / "macro_notes.csv")
    assert macro.build(tmp_path)["ok"] is True and (tmp_path / "MANIFEST.json").exists()


def test_fx_checks_find_duplicates_and_gaps(tmp_path):
    d = pd.bdate_range("2020-01-01", periods=1200)
    df = pd.DataFrame(dict(date=d, usd_inr=np.linspace(70, 80, len(d))))
    df = pd.concat([df.iloc[:500], df.iloc[530:], df.iloc[[10]]]).sort_values("date")
    p = tmp_path / "fx.csv"; df.to_csv(p, index=False)
    _, rep = macro.load_fx(p)
    assert rep["duplicates"] == 1 and rep["ok"] is False and len(rep["gaps_over_10_days"]) == 1


@pytest.mark.parametrize("q,code", [("gold", -1), ("Gold price", -1), ("price of gold", -1), ("silver", -2),
                                    ("USD/INR", -3), ("usd inr", -3), ("dollar", -3),
                                    ("gold fund", None), ("sbi gold fund", None), ("silver etf", None), ("hdfc gold etf fof", None), ("rupee", None)])
def test_macro_phrases_are_exact(q, code):
    assert macro.resolve_macro(q) == code


@pytest.fixture(scope="module")
def app():
    return App(RulePlanner())


@need_built
def test_every_measure_on_every_series_is_verified_or_withheld_for_a_stated_reason(app):
    e = app.engine
    for code in (macro.GOLD, macro.SILVER, macro.USDINR):
        s = e.series[code]
        for m in METRICS:
            for start in (str(s.dates[0]), str(s.dates[-1] - np.timedelta64(3 * 365, "D")), str(s.dates[-1] - np.timedelta64(365, "D"))):
                kw = dict(start=start, end=str(s.dates[-1]))
                if m == "sip_xirr": kw.update(amount=5000.0, day=1)
                if m == "rolling_return": kw.update(years=1)
                r = e.compute(m, code, **kw)
                assert r.status in ("VERIFIED", "WITHHELD")
                if r.status == "WITHHELD":
                    assert "disagree" not in r.reason, (code, m, start, r.reason)
                if s.kind == "monthly" and m in ("volatility", "sip_xirr"):
                    assert r.status == "WITHHELD" and "monthly averages" in r.reason
                if code == macro.USDINR and start == str(s.dates[0]) and m not in ("sharpe", "sortino"):
                    assert r.status == "WITHHELD" and "overlaps that gap" in r.reason


@need_built
def test_gold_cagr_matches_hand_calculation_from_the_table(app):
    m = pd.read_parquet(DATA / "macro" / "metals_monthly.parquet").set_index("month")
    a, b = m.loc[pd.Timestamp("2021-04-01").date(), "gold_inr_10g"], m.loc[pd.Timestamp("2026-04-01").date(), "gold_inr_10g"]
    r = app.engine.compute("cagr", macro.GOLD, start="2021-04-01", end="2026-04-01")
    days = (pd.Timestamp("2026-04-01") - pd.Timestamp("2021-04-01")).days
    assert r.status == "VERIFIED" and abs(r.value - ((b / a) ** (365 / days) - 1)) < 1e-12


@need_built
def test_answers_name_the_source_and_never_say_invested(app):
    t, _ = app.ask("gold cagr 5 years")
    assert "RBI monthly average" in t and "price rose" in t and "invested" not in t and "latest month available: Apr 2026" in t
    assert "read NAV as the price or rate" in t
    t, _ = app.ask("usd inr rolling 1 year")
    assert "ending between 12 Apr 2023" in t                     # periods start only after the 2018-2022 gap
    t, _ = app.ask("gold volatility 3 years")
    assert t.startswith("Withheld") and "monthly averages" in t
    t, _ = app.ask("sbi gold fund cagr 3 years")
    assert "scheme 119788" in t                                   # 'gold fund' stays a fund question


def test_manifest_covers_macro_files():
    from imap.manifest import FILES
    assert {"macro/metals_monthly.parquet", "macro/usd_inr_daily.parquet", "macro/report.json", "macro_notes.csv"} <= set(FILES)


def test_excel_files_listed_once_whatever_the_case(tmp_path):
    for n in ("a.XLSX", "b.xlsx", "c.Xlsx", "d.csv"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "sub").mkdir(); (tmp_path / "sub" / "e.xlsx").write_bytes(b"x")
    assert [p.name for p in macro.xlsx_files(tmp_path)] == ["a.XLSX", "b.xlsx", "c.Xlsx"]
    assert macro.xlsx_files(tmp_path / "missing") == []
