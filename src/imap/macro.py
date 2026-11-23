"""Gold, silver (RBI Handbook monthly averages) and USD/INR (RBI reference rate), with checks.

Inputs (official, downloaded once into data/raw/rbi/):
- Handbook of Statistics tables "Monthly Average Price of Gold and Silver in Domestic and Foreign Markets"
  (several editions; each covers about five years). Newest edition wins where months overlap; every overlap
  disagreement is reported, never silently resolved.
- RBI reference rate archive, USD (CSV built from the archive page). RBI's archive has no rows from July 2018
  to about April 2022 (FBIL took over the reference rate on 10 July 2018); that gap is reported, not filled.
Run: python macro.py (project root). Writes data/macro/{metals_monthly,usd_inr_daily}.parquet and a report.
"""
from __future__ import annotations
import datetime as dt, json, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2] / "data"
MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
TITLE = "MONTHLY AVERAGE PRICE OF GOLD AND SILVER"
COLS = ["gold_inr_10g", "gold_usd_oz", "gold_london_inr_10g", "gold_spread_inr", "silver_inr_kg", "silver_usc_oz", "silver_ny_inr_kg", "silver_spread_inr"]
SPREAD_TOL = 0.05     # rupees; the table prints 2 decimals


class MacroError(RuntimeError):
    pass


def _rows(path: Path) -> list[list]:
    """All cell values of the first sheet. The workbook is closed afterwards: read-only workbooks keep the file open
    until closed, and on Windows an open file cannot be replaced or moved (found from a ResourceWarning, 2026-11-23)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb.active
        if ws is None:
            raise MacroError(f"{path.name}: workbook has no sheet")
        return [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def xlsx_files(folder: Path) -> list[Path]:
    """Excel files directly in `folder`, each once. (Globbing '*.XLSX' and '*.xlsx' separately lists every file twice
    on Windows, where file names ignore case: found by a test on Ram's machine, 2026-11-23.)"""
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".xlsx") if folder.is_dir() else []


def parse_handbook(path: Path) -> tuple[pd.DataFrame, list[str]]:
    rows = _rows(path)
    text = " ".join(str(c) for r in rows[:5] for c in r if c)
    m = re.search(r"TABLE\s+(\d+)", text.upper())
    if TITLE not in text.upper() or not m:
        raise MacroError(f"{path.name}: not the gold and silver table (first rows: {text[:120]!r})")
    if "per 10gms" not in text.replace(" ", "").replace(".", "").lower().replace("10gms", "10gms") and "10gms" not in text.replace(" ", ""):
        raise MacroError(f"{path.name}: unit row not found (expected Rs per 10gms / Rs per kg)")
    table = int(m.group(1)); out: list[dict] = []; notes: list[str] = []; fy: int | None = None; months_seen: list[str] = []; n_avg = 0
    for r in rows:
        lab = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
        if re.fullmatch(r"\d{4}-\d{2}", lab):
            fy = int(lab[:4]); months_seen = []; continue
        if fy is None: continue
        if lab.lower().startswith("average") and months_seen:
            got = [x for x in out if x["file"] == path.name][-len(months_seen):]
            for c, v in zip(COLS, r[2:10], strict=True):
                mean = sum(float(x[c]) for x in got) / len(got)
                if not isinstance(v, (int, float)) or abs(mean - v) > SPREAD_TOL:
                    notes.append(f"{fy}-{(fy + 1) % 100:02d} {c}: printed average {v} != mean of its months {mean:.2f}")
            n_avg += 1; continue
        if lab in MONTHS:
            vals = r[2:10]
            if any(not isinstance(v, (int, float)) for v in vals):
                raise MacroError(f"{path.name}: non-numeric value in {lab} {fy}: {vals}")
            if months_seen and MONTHS.index(lab) != MONTHS.index(months_seen[-1]) + 1:
                raise MacroError(f"{path.name}: months out of order in {fy}: {months_seen[-1]} then {lab}")
            months_seen.append(lab)
            year = fy if MONTHS.index(lab) < 9 else fy + 1
            out.append(dict(month=dt.date(year, (MONTHS.index(lab) + 3) % 12 + 1, 1), **dict(zip(COLS, map(float, vals), strict=True)), table=table, file=path.name))
    df = pd.DataFrame(out)
    if df.empty:
        raise MacroError(f"{path.name}: no monthly rows found")
    if n_avg < 1:
        raise MacroError(f"{path.name}: no Average rows found, so the months cannot be cross-checked")
    return df, notes


def check_spreads(df: pd.DataFrame) -> list[str]:
    bad = []
    for _, r in df.iterrows():
        if abs(r.gold_inr_10g - r.gold_london_inr_10g - r.gold_spread_inr) > SPREAD_TOL:
            bad.append(f"Table {r.table} {r.month:%b %Y}: gold spread {r.gold_spread_inr} != Mumbai - London ({r.gold_inr_10g - r.gold_london_inr_10g:.2f})")
        if abs(r.silver_inr_kg - r.silver_ny_inr_kg - r.silver_spread_inr) > SPREAD_TOL:
            bad.append(f"Table {r.table} {r.month:%b %Y}: silver spread {r.silver_spread_inr} != Mumbai - New York ({r.silver_inr_kg - r.silver_ny_inr_kg:.2f})")
    return bad


def combine(parts: list[pd.DataFrame]) -> tuple[pd.DataFrame, list[str]]:
    """Newest table wins; report every month where editions disagree on any price column."""
    allp = pd.concat(parts, ignore_index=True)
    conflicts = []
    for mth, g in allp.groupby("month"):
        if len(g) > 1:
            for c in COLS:
                vals = sorted(set(round(v, 2) for v in g[c]))
                if len(vals) > 1:
                    conflicts.append(f"{mth:%b %Y} {c}: " + ", ".join(f"Table {t}={round(v, 2)}" for t, v in zip(g.table, g[c], strict=True)))
    best = allp.sort_values("table").groupby("month").tail(1).sort_values("month").reset_index(drop=True)
    return best, conflicts


def load_metals(raw: Path) -> tuple[pd.DataFrame, dict]:
    files = xlsx_files(raw)
    parts: list[pd.DataFrame] = []
    rep: dict = dict(files=[], spread_errors=[], edition_conflicts=[], gaps=[])
    for f in files:
        try:
            df, notes = parse_handbook(Path(f))
        except MacroError as e:
            rep["files"].append(dict(file=Path(f).name, ok=False, error=str(e))); continue
        rep.setdefault("average_mismatches", []).extend(f"Table {int(df.table.iloc[0])} {n}" for n in notes)
        rep["files"].append(dict(file=Path(f).name, ok=True, average_rows_checked=True, table=int(df.table.iloc[0]), months=len(df),
                                 first=f"{df.month.min():%b %Y}", last=f"{df.month.max():%b %Y}"))
        parts.append(df)
    if not parts:
        raise MacroError("no gold/silver table could be read")
    best, conflicts = combine(parts)
    rep["edition_conflicts"] = conflicts
    rep["spread_errors"] = check_spreads(pd.concat(parts))                # report for every edition
    rep["spread_errors_in_kept_rows"] = check_spreads(best)
    m = pd.to_datetime(best.month)
    exp = pd.date_range(m.min(), m.max(), freq="MS")
    rep["gaps"] = [f"{x:%b %Y}" for x in exp.difference(pd.DatetimeIndex(m))]
    rep["months"] = len(best); rep["first"] = f"{m.min():%b %Y}"; rep["last"] = f"{m.max():%b %Y}"
    return best, rep


def load_fx(csv_path: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(csv_path, parse_dates=["date"])
    if list(df.columns) != ["date", "usd_inr"]:
        raise MacroError(f"unexpected columns {list(df.columns)}")
    rep = dict(rows=len(df), first=str(df.date.min().date()), last=str(df.date.max().date()))
    rep["duplicates"] = int(df.date.duplicated().sum())
    rep["sorted"] = bool(df.date.is_monotonic_increasing)
    rep["non_positive"] = int((df.usd_inr <= 0).sum())
    ch = df.usd_inr.pct_change().abs()
    rep["daily_moves_over_3pct"] = [f"{d.date()} {c:.1%}" for d, c in zip(df.date[ch > 0.03], ch[ch > 0.03], strict=True)]
    gap = df.date.diff().dt.days
    rep["gaps_over_10_days"] = [f"{a.date()} to {b.date()} ({int(n)} days)" for a, b, n in
                                zip(df.date.shift(1)[gap > 10], df.date[gap > 10], gap[gap > 10], strict=True)]
    # gaps are reported and enforced later (any measure whose window overlaps a gap is withheld); they do not stop the build
    ok = rep["duplicates"] == 0 and rep["sorted"] and rep["non_positive"] == 0 and len(df) > 1000
    rep["ok"] = ok
    return df, rep


def reviewed(root: Path) -> pd.DataFrame:
    """data/macro_notes.csv: source inconsistencies a person has looked at, with the evidence. Columns:
    month (YYYY-MM), table, field, note. A kept-row inconsistency NOT listed here stops the build."""
    p = root / "macro_notes.csv"
    return pd.read_csv(p, dtype=str) if p.exists() else pd.DataFrame(columns=["month", "table", "field", "note"])


def _key(msg: str) -> tuple[str, str, str]:
    m = re.match(r"Table (\d+) (\w{3} \d{4}): (gold|silver)", msg)
    if m is None:
        raise MacroError(f"unexpected check message: {msg!r}")
    return m.group(1), dt.datetime.strptime(m.group(2), "%b %Y").strftime("%Y-%m"), m.group(3) + "_spread_inr"


TBILL_TENOR = 91
YIELD_TOL = 0.03          # percentage points: the cut-off price is printed to 2 decimals (0.005 of price ~ 0.02pp of yield)


def parse_tbill_handbook(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """One edition of the Handbook table 'Auctions of 91-Day Government of India Treasury Bills'.
    Columns are found by their header text, not position (editions add and drop columns). Every row's printed
    yield is re-derived from its cut-off price: y = (100/p - 1) * 365/91 * 100 (RBI: actual/365)."""
    rows = _rows(path)
    title = " ".join(str(c) for r in rows[:4] for c in r if c)
    if "91-DAY GOVERNMENT OF INDIA TREASURY BILLS" not in title.upper():
        raise MacroError(f"{path.name}: not the 91-day T-bill auction table")
    hdr = next((r for r in rows[:10] if any(isinstance(c, str) and "Implicit Yield" in c for c in r)), None)
    if hdr is None:
        raise MacroError(f"{path.name}: no 'Implicit Yield' header")
    norm = [re.sub(r"\s+", " ", str(c)).strip().lower() if c is not None else "" for c in hdr]
    yc = next(i for i, c in enumerate(norm) if c.startswith("implicit yield"))
    pc = next(i for i, c in enumerate(norm) if c.startswith("cut-off price"))
    dc = next((i for i, c in enumerate(norm) if c.startswith("date of auction")), None)
    if dc is None or not dc < pc < yc:
        raise MacroError(f"{path.name}: expected columns in the order date of auction ... cut-off price, implicit yield")
    out: list[dict] = []; notes: list[str] = []
    for r in rows:
        d = r[dc] if len(r) > dc else None
        if isinstance(d, str) and re.fullmatch(r"\d{2}-[A-Z][a-z]{2}-\d{4}", d.strip()):
            d = dt.datetime.strptime(d.strip(), "%d-%b-%Y")
        if not isinstance(d, dt.datetime):
            continue
        p, y = r[pc] if len(r) > pc else None, r[yc] if len(r) > yc else None
        if not isinstance(y, (int, float)) or not isinstance(p, (int, float)):
            notes.append(f"{d:%d %b %Y}: no yield printed ({y!r}); auction skipped"); continue
        implied = (100 / p - 1) * 365 / TBILL_TENOR * 100
        if abs(implied - y) > YIELD_TOL:
            raise MacroError(f"{path.name} {d:%d %b %Y}: printed yield {y} but price {p} implies {implied:.4f}")
        out.append(dict(date=pd.Timestamp(d), yield_pct=float(y), price=float(p), file=path.name))
    if not out:
        raise MacroError(f"{path.name}: no auction rows")
    return pd.DataFrame(out), notes


_MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_tbill_bulletin(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """RBI Bulletin 'No. 26: Auctions of Treasury Bills', 91-day block only. Dates are printed like 'Aug. 5' under a
    fiscal-year row ('2026-27'). Some issues store them as Excel dates read the wrong way round ('June 3' became
    2003-06-01): those are decoded (day = year - 2000) and listed in the notes, and must then agree with the
    Handbook where the two overlap, or the build stops."""
    rows = _rows(path)
    if not any(isinstance(c, str) and "Auctions of Treasury Bills" in c for r in rows[:4] for c in r):
        raise MacroError(f"{path.name}: not the Bulletin T-bill auction table")
    hdr = next(r for r in rows[:8] if any(isinstance(c, str) and "Implicit Yield" in c for c in r))
    norm = [re.sub(r"\s+", " ", str(c)).strip().lower() if c is not None else "" for c in hdr]
    dc = norm.index("date of auction"); pc = next(i for i, c in enumerate(norm) if c.startswith("cut-off price"))
    yc = next(i for i, c in enumerate(norm) if c.startswith("implicit yield"))
    out: list[dict] = []; notes: list[str] = []; block = None; fy: int | None = None
    for r in rows:
        lab = r[dc] if len(r) > dc else None
        if isinstance(lab, str) and "Treasury Bills" in lab:
            block = lab.split("-")[0].strip(); continue
        if isinstance(lab, str) and re.fullmatch(r"\d{4}-\d{2}", lab.strip()):
            fy = int(lab[:4]); continue
        if block != "91" or fy is None or lab is None:
            continue
        if isinstance(lab, dt.datetime) and lab.year in (fy, fy + 1):
            mon, day = lab.month, lab.day
        elif isinstance(lab, dt.datetime):
            if lab.day != 1 or not 2001 <= lab.year <= 2031:
                raise MacroError(f"{path.name}: date cell {lab} is outside fiscal year {fy} and not a swapped day")
            mon, day = lab.month, lab.year - 2000
            notes.append(f"{path.name}: date cell {lab:%Y-%m-%d} read as {day} {list(_MON)[mon - 1]} (Excel had swapped day and year)")
        else:
            m = re.fullmatch(r"([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2})", str(lab).strip())
            if not m:
                continue
            mon, day = _MON[m.group(1)], int(m.group(2))
        d = dt.datetime(fy if mon >= 4 else fy + 1, mon, day)
        p, y = r[pc], r[yc]
        if not isinstance(y, (int, float)) or not isinstance(p, (int, float)):
            notes.append(f"{d:%d %b %Y}: no yield printed ({y!r}); auction skipped"); continue
        implied = (100 / p - 1) * 365 / TBILL_TENOR * 100
        if abs(implied - y) > YIELD_TOL:
            raise MacroError(f"{path.name} {d:%d %b %Y}: printed yield {y} but price {p} implies {implied:.4f}")
        out.append(dict(date=pd.Timestamp(d), yield_pct=float(y), price=float(p), file=path.name))
    if not out:
        raise MacroError(f"{path.name}: no 91-day auction rows")
    return pd.DataFrame(out), notes


def build_tbill(raw: Path) -> tuple[pd.DataFrame | None, dict]:
    """Handbook editions (raw/rbi/tbill/*.XLSX) first; Bulletin issues (raw/rbi/tbill/bulletin/) only add later weeks.
    Every date in both sources must agree on the yield."""
    files = xlsx_files(raw)
    if not files:
        return None, dict(ok=True, missing=True)
    parts: list[pd.DataFrame] = []
    rep: dict = dict(files=[], skipped=[], conflicts=[])
    for f in files:
        df, notes = parse_tbill_handbook(f)
        parts.append(df); rep["skipped"] += notes
        rep["files"].append(dict(file=f.name, auctions=len(df), first=str(df.date.min().date()), last=str(df.date.max().date())))
    hb_files = len(parts)
    for f in xlsx_files(raw / "bulletin"):
        df, notes = parse_tbill_bulletin(f)
        parts.append(df); rep["skipped"] += [n for n in notes if "skipped" in n]
        rep.setdefault("decoded_dates", []).extend(n for n in notes if "swapped" in n)
        rep["files"].append(dict(file=f.name, source="bulletin", auctions=len(df), first=str(df.date.min().date()), last=str(df.date.max().date())))
    allp = pd.concat(parts, ignore_index=True)
    hb_dates = set(pd.concat(parts[:hb_files]).date) if hb_files else set()
    rep["bulletin_overlap_checked"] = int(sum(d in hb_dates for p in parts[hb_files:] for d in p.date))
    for d, g in allp.groupby("date"):
        if g.yield_pct.nunique() > 1:
            rep["conflicts"].append(f"{pd.Timestamp(str(d)).date()}: " + ", ".join(f"{a}={b}" for a, b in zip(g.file, g.yield_pct, strict=True)))
    best = allp.drop_duplicates("date", keep="first").sort_values("date")[["date", "yield_pct"]].reset_index(drop=True)
    return best, rep


def load_tbill(csv_path: Path) -> tuple[pd.DataFrame, dict]:
    """RBI 91-day T-bill auction cut-off yields: CSV with columns date (auction date), yield_pct (% a year).
    Checked: sorted, no duplicate dates, yields inside 0-25%, weekly cadence (any gap over 14 days is reported;
    Sharpe/Sortino windows that need a rate older than 28 days are withheld by the engines)."""
    df = pd.read_csv(csv_path, parse_dates=["date"])
    if list(df.columns) != ["date", "yield_pct"]:
        raise MacroError(f"{csv_path.name}: expected columns date, yield_pct; got {list(df.columns)}")
    rep: dict = dict(file=csv_path.name, rows=len(df), first=str(df.date.min().date()), last=str(df.date.max().date()))
    rep["duplicates"] = int(df.date.duplicated().sum()); rep["sorted"] = bool(df.date.is_monotonic_increasing)
    rep["out_of_range"] = int((~df.yield_pct.between(0, 25)).sum())
    ch = df.yield_pct.diff().abs()
    rep["weekly_moves_over_100bp"] = [f"{d.date()} {c:.2f}pp" for d, c in zip(df.date[ch > 1], ch[ch > 1], strict=True)]
    gap = df.date.diff().dt.days
    rep["gaps_over_14_days"] = [f"{a.date()} to {b.date()} ({int(n)} days)" for a, b, n in
                                zip(df.date.shift(1)[gap > 14], df.date[gap > 14], gap[gap > 14], strict=True)]
    rep["ok"] = rep["duplicates"] == 0 and rep["sorted"] and rep["out_of_range"] == 0 and len(df) >= 52
    return df, rep


def build(root: Path = ROOT) -> dict:
    raw = root / "raw" / "rbi"; out = root / "macro"; out.mkdir(exist_ok=True)
    metals, mrep = load_metals(raw)
    fxfiles = sorted(raw.glob("rbi_reference_rate_USD_*.csv"))
    if not fxfiles:
        raise MacroError("no USD reference rate CSV in data/raw/rbi/")
    fx, frep = load_fx(fxfiles[-1])
    rv = reviewed(root); known = {(r.table, r.month, r.field) for r in rv.itertuples()}
    mrep["unreviewed_in_kept_rows"] = [e for e in mrep["spread_errors_in_kept_rows"] if _key(e) not in known]
    mrep["reviewed_notes"] = rv.to_dict("records")
    ok = (not mrep["unreviewed_in_kept_rows"] and not mrep["gaps"] and not mrep.get("average_mismatches") and frep["ok"])
    tb, trep = build_tbill(raw / "tbill")
    if tb is not None:
        tmp = out / "_tbill_check.csv"; tb.to_csv(tmp, index=False)
        _, chk = load_tbill(tmp); tmp.unlink(); trep.update(chk)            # same sorted/duplicate/range/gap checks
        trep["ok"] = chk["ok"] and not trep["conflicts"]
    ok = ok and trep["ok"]
    rep = dict(built_at=dt.datetime.now().isoformat(timespec="seconds"), ok=ok, metals=mrep, fx=frep, tbill=trep)
    if ok:                           # the outputs must also meet their data contracts before anything is written
        from . import contracts as C
        try:
            C.check(C.METALS, metals); C.check(C.FX, fx)
            if tb is not None: C.check(C.TBILL, tb)
        except C.ContractError as e:
            ok = False; rep["ok"] = False; rep["contract_error"] = str(e)
    if not ok:                       # leave any earlier good build (and the manifest) untouched
        (out / "report_failed.json").write_text(json.dumps(rep, indent=1, default=str))
        return rep
    metals.to_parquet(out / "metals_monthly.parquet", index=False); fx.to_parquet(out / "usd_inr_daily.parquet", index=False)
    if tb is not None: tb.to_parquet(out / "tbill_91d.parquet", index=False)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    from .manifest import write
    write(root, f"macro build {rep['built_at']}: gold/silver {mrep['first']}..{mrep['last']}, USD/INR {frep['first']}..{frep['last']}")
    return rep


def main():
    r = build()
    m, f = r["metals"], r["fx"]
    for x in m["files"]:
        print(("OK   " if x["ok"] else "FAIL ") + x["file"] + "  " + (f"Table {x['table']}: {x['months']} months, {x['first']} to {x['last']}" if x["ok"] else x["error"]))
    print(f"Gold/silver: {m['months']} months, {m['first']} to {m['last']}; missing months: {m['gaps'] or 'none'}")
    print(f"Edition disagreements: {len(m['edition_conflicts'])}"); [print("  " + c) for c in m["edition_conflicts"][:12]]
    print(f"Average rows: every fiscal-year Average row checked against its months; mismatches: {len(m.get('average_mismatches', []))}")
    [print("  " + c) for c in m.get("average_mismatches", [])]
    print(f"Spread errors in source tables: {len(m['spread_errors'])} (in rows kept: {len(m['spread_errors_in_kept_rows'])})")
    [print("  " + c) for c in m["spread_errors"][:12]]
    print(f"Not yet reviewed (stop the build): {m['unreviewed_in_kept_rows'] or 'none'}")
    print(f"USD/INR: {f['rows']} days, {f['first']} to {f['last']}; gaps over 10 days: {f['gaps_over_10_days'] or 'none'}; daily moves over 3%: {len(f['daily_moves_over_3pct'])}")
    t = r.get("tbill", {})
    print("T-bill 91-day yields: not downloaded yet (Sharpe and Sortino stay withheld)" if t.get("missing") else
          f"T-bill 91-day yields: {t['rows']} auctions, {t['first']} to {t['last']}; gaps over 14 days: {t['gaps_over_14_days'] or 'none'}; "
          f"weekly moves over 1 percentage point: {len(t['weekly_moves_over_100bp'])}")
    print("BUILT (manifest updated)" if r["ok"] else "NOT BUILT (see data/macro/report_failed.json); earlier data left as it was")


if __name__ == "__main__":
    main()


# ---- use in the app --------------------------------------------------------------------------------------
GOLD, SILVER, USDINR = -1, -2, -3
NAMES = {GOLD: "Gold, Mumbai (RBI monthly average, Rs per 10 g)",
         SILVER: "Silver, Mumbai (RBI monthly average, Rs per kg)",
         USDINR: "US dollar in rupees (RBI reference rate)"}
LEVEL = {GOLD: "price", SILVER: "price", USDINR: "rate"}
_ALIASES = {GOLD: {"gold", "gold price", "gold rate", "price of gold", "mumbai gold"},
            SILVER: {"silver", "silver price", "silver rate", "price of silver", "mumbai silver"},
            USDINR: {"usd inr", "usdinr", "usd to inr", "inr usd", "dollar", "us dollar", "dollar rupee", "rupee dollar",
                     "dollar to rupee", "rupee vs dollar", "dollar vs rupee", "usd"}}


def resolve_macro(query: str) -> int | None:
    """Exact phrases only. 'gold fund', 'gold etf', 'silver etf fof' are funds and go to the fund resolver."""
    ws = re.sub(r"[^a-z ]+", " ", query.lower()).split()
    q = " ".join(w for w in ws if w not in {"the", "of", "in", "india", "indian", "rate", "price"} or len(ws) == 1)
    for code, names in _ALIASES.items():
        if q in {re.sub(r"\b(the|of|in|india|indian|rate|price)\b", " ", n).strip().replace("  ", " ") for n in names} | names:
            return code
    return None


def load_risk_free(root: Path = ROOT) -> pd.DataFrame | None:
    p = root / "macro" / "tbill_91d.parquet"
    if not p.exists():
        return None
    from . import contracts as C
    return C.check(C.TBILL, pd.read_parquet(p))


def load_series(root: Path = ROOT):
    """-> ({code: Series}, rows for engine B with columns scheme_code, date, nav). Empty if not built."""
    import numpy as np
    from .series import Series
    d = root / "macro"
    if not (d / "metals_monthly.parquet").exists():
        return {}, pd.DataFrame(columns=["scheme_code", "date", "nav"])
    from . import contracts as C
    m = C.check(C.METALS, pd.read_parquet(d / "metals_monthly.parquet")); fx = C.check(C.FX, pd.read_parquet(d / "usd_inr_daily.parquet"))
    rep = json.loads((d / "report.json").read_text())
    last = pd.Timestamp(m.month.max()).strftime("%b %Y")
    synth = "SYNTHETIC DEMO DATA, not RBI data. " if rep.get("synthetic") else ""
    mnote = (synth + f"Monthly average prices from the RBI Handbook (each month is dated on its 1st); latest month available: {last}. "
             "The fall and rise within a month are not visible in averages.")
    out: dict[int, Series] = {}; rows = []
    for code, col in ((GOLD, "gold_inr_10g"), (SILVER, "silver_inr_kg")):
        dates = pd.to_datetime(m.month).to_numpy(dtype="datetime64[D]")
        out[code] = Series(code, dates, m[col].to_numpy(float), kind="monthly", notes=(mnote,))
        rows.append(pd.DataFrame(dict(scheme_code=code, date=pd.to_datetime(m.month), nav=m[col].astype(float))))
    fd = fx.date.to_numpy(dtype="datetime64[D]"); gaps = []
    for g in rep["fx"]["gaps_over_10_days"]:
        a, b = g.split(" (")[0].split(" to ")
        gaps.append((np.datetime64(a), np.datetime64(b)))
    fnote = synth + f"RBI reference rate; latest day available: {pd.Timestamp(fx.date.max()):%d %b %Y}. RBI's archive has no rates from {gaps[-1][0]} to {gaps[-1][1]} (FBIL published the reference rate then)." if gaps else synth + "RBI reference rate."
    out[USDINR] = Series(USDINR, fd, fx.usd_inr.to_numpy(float), kind="daily_fx", gaps=tuple(gaps), notes=(fnote,))
    rows.append(pd.DataFrame(dict(scheme_code=USDINR, date=fx.date, nav=fx.usd_inr.astype(float))))
    return out, pd.concat(rows, ignore_index=True)
