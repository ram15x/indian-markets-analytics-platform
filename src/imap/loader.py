"""Load the AMFI NAV archive into the v1 universe: active Direct+Growth schemes.

The raw archive is read-only input. Output is Parquet; nothing here adjusts values.
"""
from __future__ import annotations
import re, sqlite3
from pathlib import Path
import pandas as pd

ACTIVE_FROM = "2026-11-01"   # last NAV on/after this date = active
_DIRECT = re.compile(r"\bdirect\b", re.I)
_GROWTH = re.compile(r"\bgrowth\b", re.I)
_NOT_GROWTH = re.compile(r"\b(idcw|dividend|payout|reinvest|bonus)\b", re.I)


_DIV_YIELD = re.compile(r"dividend\s+yield", re.I)  # a fund category, not a payout option


def is_direct_growth(name: str) -> bool:
    n = _DIV_YIELD.sub("", name)
    return bool(_DIRECT.search(n) and _GROWTH.search(n) and not _NOT_GROWTH.search(n))


def load_universe(db_path: str | Path, active_from: str = ACTIVE_FROM) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (schemes, nav). nav columns: scheme_code, date (datetime64), nav (float)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        sch = pd.read_sql("select scheme_code, scheme_name from schemes", con)
        sch = sch[sch.scheme_name.map(is_direct_growth)]
        last = pd.read_sql("select scheme_code, max(date) as last_date, min(date) as first_date, count(*) as n_rows "
                           "from nav group by scheme_code", con)
        sch = sch.merge(last, on="scheme_code")
        sch = sch[sch.last_date >= active_from].reset_index(drop=True)
        codes = ",".join(map(str, sch.scheme_code))
        nav = pd.read_sql(f"select scheme_code, date, nav from nav where scheme_code in ({codes})", con)
    finally:
        con.close()
    nav["date"] = pd.to_datetime(nav["date"])
    nav = nav.drop_duplicates(["scheme_code", "date"]).sort_values(["scheme_code", "date"]).reset_index(drop=True)
    return sch, nav


def write_parquet(sch: pd.DataFrame, nav: pd.DataFrame, out: str | Path) -> None:
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    sch.to_parquet(out / "schemes.parquet", index=False)
    nav.to_parquet(out / "nav_raw.parquet", index=False)
