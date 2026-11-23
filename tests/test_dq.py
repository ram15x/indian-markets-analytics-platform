import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd
from imap import dq
from imap.loader import is_direct_growth


def series(v):
    d = pd.date_range("2020-01-01", periods=len(v), freq="D")
    return pd.DataFrame(dict(scheme_code=1, date=d, nav=np.asarray(v, float)))


def base(n=300):
    return 100 * np.cumprod(np.full(n, 1.0004))


def test_scale_up_is_adjusted_continuous():
    v = base(); v[150:] *= 100
    df = series(v); ev, ad = dq.run(df); out = dq.apply(df, ev, ad)
    assert list(ev.kind) == ["SCALE_CHANGE"] and ad.k.iloc[0] == 100
    assert np.allclose(out.nav_adj.values, base() * 100)
    assert (out.nav == df.nav).all()           # raw untouched


def test_scale_down_is_adjusted_continuous():
    v = base(); v[150:] /= 10
    df = series(v); ev, ad = dq.run(df); out = dq.apply(df, ev, ad)
    assert np.allclose(out.nav_adj.values, base() / 10)


def test_single_day_glitch_is_excluded_not_adjusted():
    v = base(); v[100] *= 2
    df = series(v); ev, ad = dq.run(df); out = dq.apply(df, ev, ad)
    assert list(ev.kind) == ["BAD_VALUE"] and len(ad) == 0
    assert out.excluded.sum() == 1 and np.isnan(out.nav_adj.iloc[100])


def test_real_crash_not_adjusted():
    v = base(); v[150:] *= 0.78
    ev, ad = dq.run(series(v))
    assert list(ev.kind) == ["LARGE_MOVE"] and len(ad) == 0


def test_clean_series_has_no_events():
    ev, ad = dq.run(series(base()))
    assert len(ev) == 0 and len(ad) == 0


def test_name_filter():
    assert is_direct_growth("HDFC Dividend Yield Fund - Growth Option Direct Plan")
    assert is_direct_growth("SBI Small Cap Fund - Direct Plan - Growth")
    assert not is_direct_growth("Nippon India Large Cap Fund - Direct Plan Growth Plan - Bonus Option")
    assert not is_direct_growth("X Fund - Direct Plan - IDCW")
    assert not is_direct_growth("X Fund - Regular Plan - Growth")
