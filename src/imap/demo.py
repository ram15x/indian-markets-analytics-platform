"""Synthetic demo data, so anyone can run the whole app (and CI can test the engines) without the real data.

EVERYTHING HERE IS INVENTED. The funds, prices, gold, silver, dollar rate and T-bill yields are random walks from a
fixed seed. Nothing in this folder is real market data; the app says so on every page when it runs on it.
The real data (AMFI, RBI) cannot be published because reuse terms are unverified (docs/FEASIBILITY.md).

Run:  python serve.py --demo      (builds demo_data/ the first time)
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from . import manifest

SEED = 20261123
LAST_DAY = "2026-11-20"
SOURCE = "synthetic demo data (src/imap/demo.py): invented, not real prices"

# code, name, yearly drift, yearly volatility, first date
FUNDS = [
    (900001, "DEMO Large Cap Fund - Direct Plan - Growth", 0.12, 0.15, "2013-01-02"),
    (900002, "DEMO Mid Cap Fund - Direct Plan - Growth", 0.13, 0.19, "2013-01-02"),
    (900003, "DEMO Small Cap Fund - Direct Plan - Growth", 0.15, 0.23, "2013-01-02"),
    (900004, "DEMO Small Cap Opportunities - Direct Plan - Growth", 0.14, 0.24, "2015-06-01"),
    (900005, "DEMO Flexi Cap Fund - Direct Plan - Growth", 0.14, 0.16, "2013-01-02"),
    (900006, "DEMO Index Fund - Direct Plan - Growth", 0.11, 0.15, "2013-01-02"),
    (900007, "DEMO Value Fund - Direct Plan - Growth", 0.13, 0.17, "2014-03-03"),
    (900008, "DEMO Focused Fund - Direct Plan - Growth", 0.15, 0.18, "2016-01-04"),
    (900009, "DEMO Balanced Fund - Direct Plan - Growth", 0.09, 0.09, "2013-01-02"),
    (900010, "DEMO Short Duration Fund - Direct Plan - Growth", 0.07, 0.01, "2013-01-02"),
    (900011, "DEMO Tax Saver Fund - Direct Plan - Growth", 0.13, 0.17, "2013-01-02"),
    (900012, "DEMO New Fund - Direct Plan - Growth", 0.12, 0.14, "2024-02-01"),   # short history on purpose
]


def _walk(rng, n: int, drift: float, vol: float, market: np.ndarray, beta: float = 0.8) -> np.ndarray:
    dt = 1 / 252
    own = rng.normal(0, 1, n) * vol * np.sqrt(dt) * np.sqrt(max(1 - beta ** 2 * 0.5, 0.1))
    r = (drift - 0.5 * vol ** 2) * dt + beta * market + own
    return np.exp(np.cumsum(r))


def build(root: Path) -> Path:
    """Write the demo data files and a manifest into root. Deterministic: same seed, same bytes of content."""
    root = Path(root); (root / "macro").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    days = pd.bdate_range("2013-01-02", LAST_DAY)
    n = len(days)
    mkt = rng.normal(0.10 / 252, 0.13 / np.sqrt(252), n)                       # one market factor shared by the equity funds
    crash = np.asarray((days >= pd.Timestamp("2020-02-20")) & (days <= pd.Timestamp("2020-03-23")))
    mkt[crash] += -0.011                                                       # a sharp fall, then the walk recovers on its own
    rows, schemes = [], []
    for code, name, drift, vol, first in FUNDS:
        mask = np.asarray(days >= pd.Timestamp(first))
        d = days[mask]
        beta = 0.0 if vol < 0.02 else (0.35 if vol < 0.1 else 0.85)
        nav = np.round(10 * _walk(rng, len(d), drift, vol, mkt[mask] * (beta if beta else 0), beta=1.0 if beta else 0.0), 4)
        nav = np.where(nav > 0, nav, 0.0001)
        rows.append(pd.DataFrame(dict(scheme_code=np.int64(code), date=d.to_numpy(dtype="datetime64[us]"), nav=nav)))
        schemes.append(dict(scheme_code=code, scheme_name=name, last_date=str(d[-1].date()), first_date=str(d[0].date()), n_rows=len(d)))
    pd.concat(rows, ignore_index=True).to_parquet(root / "nav_raw.parquet", index=False)
    pd.DataFrame(schemes).astype(dict(scheme_code="int64", n_rows="int64")).to_parquet(root / "schemes.parquet", index=False)
    pd.DataFrame(dict(scheme_code=pd.Series(dtype="int64"), date=pd.Series(dtype="datetime64[ms]"), kind=pd.Series(dtype="str"),
                      ratio=pd.Series(dtype="float64"), k=pd.Series(dtype="float64"), direction=pd.Series(dtype="float64"),
                      exclude_rows=pd.Series(dtype="float64"), span_days=pd.Series(dtype="float64"),
                      gap_days=pd.Series(dtype="float64"), run=pd.Series(dtype="float64"))).to_parquet(root / "dq_events.parquet", index=False)
    pd.DataFrame(dict(scheme_code=pd.Series(dtype="int64"), effective_date=pd.Series(dtype="datetime64[ms]"),
                      factor=pd.Series(dtype="float64"), reason=pd.Series(dtype="str"), k=pd.Series(dtype="float64"))).to_parquet(root / "dq_adjustments.parquet", index=False)
    (root / "renames.csv").write_text("old_name,target_code,new_name_in_archive,effective,source_url,label\n", encoding="utf-8")
    # gold and silver: monthly averages, Apr 2017 to Apr 2026 (like the real RBI series, which stops months before fund prices)
    months = pd.date_range("2017-04-01", "2026-04-01", freq="MS")
    g = 29000 * np.exp(np.cumsum(rng.normal(0.008, 0.035, len(months)))); s = 42000 * np.exp(np.cumsum(rng.normal(0.007, 0.06, len(months))))
    usd = 1266 * np.exp(np.cumsum(rng.normal(0.003, 0.03, len(months))))
    pd.DataFrame(dict(month=pd.Series(list(months.date), dtype=object), gold_inr_10g=np.round(g, 2), gold_usd_oz=np.round(usd, 2),
                      gold_london_inr_10g=np.round(g * 0.9, 2), gold_spread_inr=np.round(g * 0.1, 2), silver_inr_kg=np.round(s, 2),
                      silver_usc_oz=np.round(s / 30, 2), silver_ny_inr_kg=np.round(s * 0.9, 2), silver_spread_inr=np.round(s * 0.1, 2),
                      table=np.int64(162), file="synthetic")).to_parquet(root / "macro" / "metals_monthly.parquet", index=False)
    fxd = 54.8 * np.exp(np.cumsum(rng.normal(0.00007, 0.0030, n)))
    pd.DataFrame(dict(date=days.to_numpy(dtype="datetime64[ns]"), usd_inr=np.round(fxd, 4))).to_parquet(root / "macro" / "usd_inr_daily.parquet", index=False)
    weeks = pd.date_range("2015-07-01", "2026-09-30", freq="W-WED")
    ty = np.clip(6.5 + np.cumsum(rng.normal(0, 0.06, len(weeks))) * 0.3, 3.0, 9.0)
    pd.DataFrame(dict(date=weeks.to_numpy(dtype="datetime64[ns]"), yield_pct=np.round(ty, 4))).to_parquet(root / "macro" / "tbill_91d.parquet", index=False)
    (root / "macro" / "report.json").write_text(json.dumps(dict(fx=dict(gaps_over_10_days=[]), synthetic=True)), encoding="utf-8")
    manifest.write(root, SOURCE)
    return root


def is_demo(m: dict | None) -> bool:
    return m is not None and str(m.get("source", "")).startswith("synthetic demo data")
