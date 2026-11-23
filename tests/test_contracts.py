"""Data contracts: the real files pass, and each kind of bad content is refused with a readable reason."""
from pathlib import Path
import pandas as pd
import pytest
from imap import contracts as C

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def nav():
    return pd.read_parquet(DATA / "nav_raw.parquet").head(50_000)


def test_real_files_meet_contracts():
    for s, f in [(C.SCHEMES, "schemes"), (C.EVENTS, "dq_events"), (C.ADJ, "dq_adjustments")]:
        C.check(s, pd.read_parquet(DATA / f"{f}.parquet"))


@pytest.mark.parametrize("break_it,word", [
    (lambda d: pd.concat([d, d.head(1)]), "nav_raw"),                                  # duplicate (code, date)
    (lambda d: d.assign(nav=d.nav.where(d.index != d.index[5], -1.0)), "greater_than"),  # negative NAV
    (lambda d: d.assign(nav=d.nav.where(d.index != d.index[5], 5e7)), "crore"),          # absurd NAV
    (lambda d: d.assign(date=d.date.where(d.index != d.index[5], pd.Timestamp("1990-01-01"))), "outside"),
    (lambda d: d.assign(extra=1), "extra"),                                            # unexpected column
])
def test_bad_nav_refused(nav, break_it, word):
    with pytest.raises(C.ContractError, match="(?s)" + word if word != "extra" else "(?s)nav_raw"):
        C.check(C.NAV, break_it(nav))


def test_bad_schemes_and_events_refused():
    sch = pd.read_parquet(DATA / "schemes.parquet")
    with pytest.raises(C.ContractError, match="Direct"):
        C.check(C.SCHEMES, sch.assign(scheme_name=sch.scheme_name.where(sch.index != 0, "HDFC Top 100 Fund - Regular Plan - Growth")))
    with pytest.raises(C.ContractError, match="first_date after last_date"):
        C.check(C.SCHEMES, sch.assign(first_date=sch.first_date.where(sch.index != 0, "2099-01-01")))
    ev = pd.read_parquet(DATA / "dq_events.parquet")
    with pytest.raises(C.ContractError, match="isin"):
        C.check(C.EVENTS, ev.assign(kind=ev.kind.where(ev.index != 0, "MAGIC")))
    ad = pd.read_parquet(DATA / "dq_adjustments.parquet")
    with pytest.raises(C.ContractError, match="adjusts nothing"):
        C.check(C.ADJ, ad.assign(factor=1.0))


def test_bad_macro_refused():
    m = pd.read_parquet(DATA / "macro" / "metals_monthly.parquet")
    with pytest.raises(C.ContractError, match="sorted"):
        C.check(C.METALS, m.iloc[::-1])
    fx = pd.read_parquet(DATA / "macro" / "usd_inr_daily.parquet")
    with pytest.raises(C.ContractError, match="in_range"):
        C.check(C.FX, fx.assign(usd_inr=fx.usd_inr.where(fx.index != 3, 929.699)))      # decimal slip x10
