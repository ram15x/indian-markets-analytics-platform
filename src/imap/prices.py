"""End-of-day NSE equity closing prices (local, personal use only; never published).

Source: NSE's daily CM bhavcopy. Column names are matched under both the UDiFF names and the older names,
because the exact headers have not been verified from here. If the needed columns are not found, the load is
refused and the headers that were found are reported. Only the latest file is kept (data/prices/latest.parquet);
raw downloads go to data/raw/ and must not be committed to a public repo.
"""
from __future__ import annotations
import csv, datetime as dt, io, sys, time, urllib.error, urllib.request, zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2] / "data"
URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
COLS = {   # our name: accepted header names (UDiFF first, then older bhavcopy)
    "isin": ("ISIN",), "symbol": ("TckrSymb", "SYMBOL"), "series": ("SctySrs", "SERIES"),
    "close": ("ClsPric", "CLOSE", "CLOSE_PRICE"), "date": ("TradDt", "TIMESTAMP", "DATE1"),
}
MIN_ROWS = 1000
MAX_AGE_DAYS = 7


class PriceError(RuntimeError):
    pass


def _pick(header: list[str]) -> dict[str, str]:
    h = {c.strip().upper(): c for c in header}
    out: dict[str, str] = {}; missing: list[str] = []
    for k, names in COLS.items():
        hit = next((h[n.upper()] for n in names if n.upper() in h), None)
        (out.__setitem__(k, hit) if hit else missing.append(k))
    if missing:
        raise PriceError(f"columns not found: {missing}; headers in the file: {header[:40]}")
    return out


def parse(raw: bytes) -> pd.DataFrame:
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if len(names) != 1:
                raise PriceError(f"expected one CSV in the zip, found {names}")
            raw = z.read(names[0])
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))
    if not rows:
        raise PriceError("empty file")
    c = _pick(rows[0]); idx = {k: rows[0].index(v) for k, v in c.items()}
    recs = []
    for r in rows[1:]:
        if len(r) < len(rows[0]):
            continue
        try:
            close = float(r[idx["close"]].replace(",", ""))
        except ValueError:
            continue
        recs.append((r[idx["isin"]].strip(), r[idx["symbol"]].strip(), r[idx["series"]].strip(), close, r[idx["date"]].strip()))
    df = pd.DataFrame(recs, columns=["isin", "symbol", "series", "close", "date"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False, format="mixed")
    return df


def check(df: pd.DataFrame, today: dt.date) -> list[tuple[str, bool, str]]:
    g = []
    g.append(("row_count", len(df) >= MIN_ROWS, f"{len(df)} rows (min {MIN_ROWS})"))
    dates = df["date"].dropna().dt.date.unique()
    g.append(("one_trade_date", len(dates) == 1, f"trade dates in file: {sorted(map(str, dates))[:5]}"))
    newest = max(dates) if len(dates) else None
    g.append(("fresh", newest is not None and 0 <= (today - newest).days <= MAX_AGE_DAYS, f"trade date {newest}, today {today}"))
    eq = df[df.series == "EQ"]
    g.append(("eq_prices_positive", len(eq) > 500 and bool((eq.close > 0).all()), f"{len(eq)} EQ rows, {(eq.close <= 0).sum()} non-positive"))
    dup = int(eq["isin"].duplicated().sum())
    g.append(("one_eq_row_per_isin", dup == 0, f"{dup} duplicate ISINs in series EQ"))
    return g


def load(raw: bytes, root: Path = ROOT, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    try:
        df = parse(raw); gates = check(df, today)
    except PriceError as e:
        gates = [("format", False, str(e))]; df = None
    ok = all(x[1] for x in gates)
    rep = dict(ok=ok, gates=[dict(name=n, ok=o, detail=d) for n, o, d in gates], written=None)
    if ok and df is not None:
        out = root / "prices"; out.mkdir(exist_ok=True)
        tmp = out / "latest.parquet.tmp"; df.to_parquet(tmp, index=False); tmp.replace(out / "latest.parquet")
        rep["written"] = dict(rows=len(df), trade_date=str(df.date.dropna().dt.date.max()))
    return rep


def latest(root: Path = ROOT) -> pd.DataFrame | None:
    p = root / "prices" / "latest.parquet"
    return pd.read_parquet(p) if p.exists() else None


def value_holdings(rows: list[dict], prices: pd.DataFrame | None) -> dict:
    """Add close price, value and gain vs average buy price, matched by ISIN (series EQ preferred)."""
    if prices is None:
        return dict(price_date=None, note="No price file yet: run `python prices.py`. Showing cost only.")
    pref = {"EQ": 0, "BE": 1, "BZ": 2, "SM": 3, "ST": 4}
    p = prices.assign(rank=prices.series.map(lambda s: pref.get(s, 9))).sort_values("rank").drop_duplicates("isin")
    by = p.set_index("isin")
    total_cost = total_value = 0.0; priced = 0
    for r in rows:
        if r["isin"] in by.index:
            x = by.loc[r["isin"]]; r["close"] = float(x.close); r["series"] = x.series
            r["value"] = r["quantity"] * r["close"]; r["gain"] = r["value"] - r["cost"]
            r["gain_pct"] = (r["gain"] / r["cost"]) if r["cost"] else None
            total_cost += r["cost"]; total_value += r["value"]; priced += 1
        else:
            r["close"] = r["value"] = r["gain"] = r["gain_pct"] = None
    d = str(prices.date.dropna().dt.date.max())
    return dict(price_date=d, priced=priced, unpriced=len(rows) - priced, total_value_priced=total_value, total_cost_priced=total_cost,
                total_gain_priced=total_value - total_cost,
                note=f"Closing prices from NSE's end-of-day file for {d} (not live). Gain is against your average buy price "
                     f"as reported by Groww; it ignores charges, dividends and taxes.")


def fetch(day: dt.date) -> bytes | None:
    req = urllib.request.Request(URL.format(ymd=day.strftime("%Y%m%d")), headers={
        "User-Agent": "Mozilla/5.0 (personal research; one request per day)", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    today = dt.date.today()
    for back in range(0, 8):                           # weekends and holidays have no file
        d = today - dt.timedelta(days=back)
        raw = fetch(d)
        if raw:
            rawdir = ROOT / "raw"; rawdir.mkdir(exist_ok=True)
            (rawdir / f"nse_cm_bhavcopy_{d:%Y%m%d}.zip").write_bytes(raw)
            r = load(raw, today=today)
            for g in r["gates"]:
                print(("PASS " if g["ok"] else "FAIL ") + g["name"].ljust(22) + g["detail"])
            print("LOADED" if r["written"] else "NOT LOADED", r["written"] or "")
            sys.exit(0 if r["ok"] else 1)
        time.sleep(2)                                   # be gentle with NSE
    print("No NSE file found for the last 8 days."); sys.exit(1)


if __name__ == "__main__":
    main()
