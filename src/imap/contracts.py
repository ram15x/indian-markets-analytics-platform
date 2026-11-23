"""Data contracts (pandera): what every table the app loads must look like. Checked at start-up after the manifest,
so a file that is intact (manifest OK) but wrong in content (e.g. produced by a buggy build) is still refused.

The manifest proves a file was not changed; these rules check that what it contains makes sense.
"""
from __future__ import annotations
import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

DQ_KINDS = ["LARGE_MOVE", "STALE_RUN", "SCALE_CHANGE", "TRANSIENT_SHIFT", "BAD_VALUE", "GAP"]
FIRST_DAY, LAST_DAY = pd.Timestamp("2006-04-01"), pd.Timestamp("2100-01-01")
in_range = Check(lambda s: s.between(FIRST_DAY, LAST_DAY), error="date outside 2006-04-01..2100")

NAV = DataFrameSchema({
    "scheme_code": Column("int64", Check.gt(0)),
    "date": Column("datetime64[us]", in_range, coerce=True),
    "nav": Column("float64", [Check.gt(0), Check(lambda s: s.lt(1e7), error="NAV above Rs 1 crore per unit")]),
}, unique=["scheme_code", "date"], strict=True, name="nav_raw")

SCHEMES = DataFrameSchema({
    "scheme_code": Column("int64", Check.gt(0), unique=True),
    "scheme_name": Column(str, [Check.str_length(5, 200), Check(lambda s: s.str.contains("direct", case=False), error="not a Direct plan")]),
    "first_date": Column(str, Check.str_matches(r"^\d{4}-\d{2}-\d{2}$")),
    "last_date": Column(str, Check.str_matches(r"^\d{4}-\d{2}-\d{2}$")),
    "n_rows": Column("int64", Check.gt(0)),
}, checks=Check(lambda d: (d.first_date <= d.last_date), error="first_date after last_date"), strict=True, name="schemes")

EVENTS = DataFrameSchema({
    "scheme_code": Column("int64", Check.gt(0)),
    "date": Column("datetime64[ms]", in_range, coerce=True),
    "kind": Column(str, Check.isin(DQ_KINDS)),
}, strict=False, name="dq_events")

ADJ = DataFrameSchema({
    "scheme_code": Column("int64", Check.gt(0)),
    "effective_date": Column("datetime64[ms]", in_range, coerce=True),
    "factor": Column("float64", [Check.gt(0), Check(lambda s: (s - 1).abs() > 1e-9, error="factor of 1 adjusts nothing")]),
}, strict=False, name="dq_adjustments")

PRICE = [Check.gt(0), Check(lambda s: s.notna())]
METALS = DataFrameSchema({
    "month": Column(object, Check(lambda s: pd.Series(pd.to_datetime(s)).dt.day.eq(1), error="month must be dated on the 1st")),
    **{c: Column("float64", PRICE) for c in ("gold_inr_10g", "gold_usd_oz", "gold_london_inr_10g", "silver_inr_kg", "silver_usc_oz", "silver_ny_inr_kg")},
    "table": Column("int64", Check.between(100, 999)),
}, unique=["month"], strict=False, name="metals_monthly",
    checks=Check(lambda d: pd.to_datetime(d.month).is_monotonic_increasing, error="months not sorted"))

FX = DataFrameSchema({
    "date": Column("datetime64[ns]", in_range, unique=True, coerce=True),
    "usd_inr": Column("float64", Check.between(30, 300)),
}, strict=True, name="usd_inr_daily", checks=Check(lambda d: d.date.is_monotonic_increasing, error="dates not sorted"))


TBILL = DataFrameSchema({
    "date": Column("datetime64[ns]", in_range, unique=True, coerce=True),
    "yield_pct": Column("float64", Check.between(0, 25)),
}, strict=True, name="tbill_91d", checks=Check(lambda d: d.date.is_monotonic_increasing, error="dates not sorted"))


class ContractError(RuntimeError):
    pass


def check(schema: DataFrameSchema, df: pd.DataFrame) -> pd.DataFrame:
    """Validate every rule and report all failures at once (lazy), not just the first."""
    try:
        return schema.validate(df.reset_index(drop=True), lazy=True)   # fresh index: pandera's report needs unique labels
    except (pa.errors.SchemaErrors, pa.errors.SchemaError) as e:
        fc = getattr(e, "failure_cases", None)
        detail = fc.head(10).to_string() if fc is not None else str(e)
        raise ContractError(f"{schema.name}: data does not meet its contract:\n{detail}") from None
