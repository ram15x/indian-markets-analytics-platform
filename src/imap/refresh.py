"""Nightly refresh from AMFI's official daily file (NAVAll.txt), with gates that refuse a bad load.

Run on a machine that can reach amfiindia.com:  python -m imap.refresh
Raw files are kept as downloaded (data/raw/). nav_raw.parquet is only replaced when every gate passes,
via write-to-temp then rename, with the previous file kept as a backup. A report is written either way.
"""
from __future__ import annotations
import datetime as dt, json, math, os, shutil, sys, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
from . import dq

URL = "https://www.amfiindia.com/spages/NAVAll.txt"
HEADER_OLD = "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date"
HEADER_NEW = "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date"  # seen 2026-11-23
HEADERS = (HEADER_NEW, HEADER_OLD)
HEADER = HEADER_NEW
ROOT = Path(__file__).resolve().parents[2] / "data"

# gate thresholds (set before any real run; change only with a note in docs/REFRESH.md)
MIN_ROWS = 5000            # the full file has well over 10,000 scheme rows
MIN_COVERAGE = 0.90        # share of our universe present in the file
MAX_AGE_DAYS = 7           # newest NAV date in the file must be this recent
MAX_NA_SHARE = 0.02        # universe rows with no usable NAV
MAX_BIG_MOVE_SHARE = 0.02  # universe rows moving >10% vs last stored NAV (more suggests a bad file)
MAX_CONFLICT_SHARE = 0.005 # same date as stored but a different NAV


@dataclass
class Gate:
    name: str; ok: bool; detail: str


def _header(text: str) -> str:
    return text.lstrip("\ufeff").splitlines()[0].strip() if text else ""


def parse(text: str) -> pd.DataFrame:
    """Read AMFI NAVAll.txt by its header (old 6-column or new 8-column layout). Unknown layout -> empty frame."""
    head = _header(text)
    if head not in HEADERS:
        return pd.DataFrame({"scheme_code": pd.Series(dtype="int64"), "isin_growth": pd.Series(dtype=str), "isin_reinv": pd.Series(dtype=str),
                             "scheme_name": pd.Series(dtype=str), "nav": pd.Series(dtype=float), "date": pd.Series(dtype="datetime64[ns]")})
    cols = head.split(";"); n = len(cols); ix = {c: i for i, c in enumerate(cols)}
    rows = []
    for line in text.splitlines()[1:]:
        parts = [p.strip() for p in line.split(";")]
        if len(parts) != n or not parts[0].isdigit():
            continue
        try:
            d = dt.datetime.strptime(parts[ix["Date"]], "%d-%b-%Y").date()
        except ValueError:
            continue
        try:
            v = float(parts[ix["Net Asset Value"]].replace(",", ""))
        except ValueError:
            v = math.nan
        name = parts[ix["Scheme Name"]]
        if "Plan" in ix:                                   # new layout: plan and option in their own columns
            name = f"{name} - {parts[ix['Plan']]} - {parts[ix['Option']]}"
        rows.append((int(parts[0]), parts[1], parts[2], name, v, d))
    df = pd.DataFrame(rows, columns=["scheme_code", "isin_growth", "isin_reinv", "scheme_name", "nav", "date"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def check(text: str, new: pd.DataFrame, stored: pd.DataFrame, universe: set[int], today: dt.date) -> tuple[list[Gate], pd.DataFrame, dict]:
    G: list[Gate] = []
    head = _header(text)
    G.append(Gate("header", head in HEADERS, ("known AMFI layout (" + ("new, 8 columns" if head == HEADER_NEW else "old, 6 columns") + ")")
                  if head in HEADERS else (f"unknown layout; first line is {head!r}" if head else "empty file")))
    G.append(Gate("row_count", len(new) >= MIN_ROWS, f"{len(new)} scheme rows parsed (min {MIN_ROWS})"))
    dup = int(new.scheme_code.duplicated().sum())
    G.append(Gate("no_duplicate_codes", dup == 0, f"{dup} duplicate scheme codes"))
    u = new[new.scheme_code.isin(universe)].drop_duplicates("scheme_code")
    cov = len(u) / max(1, len(universe))
    G.append(Gate("universe_coverage", cov >= MIN_COVERAGE, f"{len(u)} of {len(universe)} universe schemes present ({cov:.1%}, min {MIN_COVERAGE:.0%})"))
    newest = new.date.max().date() if len(new) else None
    fresh = newest is not None and (today - newest).days <= MAX_AGE_DAYS and newest <= today
    G.append(Gate("fresh_dates", fresh, f"newest NAV date {newest}, today {today} (max age {MAX_AGE_DAYS} days, none in the future)"))
    future = int((u.date.dt.date > today).sum())
    G.append(Gate("no_future_dates", future == 0, f"{future} universe rows dated after today"))
    na = u.nav.isna() | (u.nav <= 0)
    G.append(Gate("usable_nav", na.mean() <= MAX_NA_SHARE if len(u) else False, f"{int(na.sum())} universe rows with missing or non-positive NAV (max {MAX_NA_SHARE:.0%})"))
    u = u[~na]
    last = stored.sort_values("date").groupby("scheme_code").tail(1).set_index("scheme_code")
    m = u.join(last.add_suffix("_old"), on="scheme_code")      # last holds date, nav -> date_old, nav_old
    newer = m[m.date > m.date_old]
    same = m[(m.date == m.date_old)]
    conflict = same[(same.nav / same.nav_old - 1).abs() > 1e-9]
    G.append(Gate("no_conflicts", len(conflict) <= MAX_CONFLICT_SHARE * max(1, len(u)),
                  f"{len(conflict)} schemes with the same date as stored but a different NAV (max {MAX_CONFLICT_SHARE:.1%})"))
    older = int((m.date < m.date_old).sum())
    move = (newer.nav / newer.nav_old - 1).abs()
    big = int((move > 0.10).sum())
    G.append(Gate("no_systemic_jumps", big <= MAX_BIG_MOVE_SHARE * max(1, len(newer)),
                  f"{big} of {len(newer)} updated schemes moved more than 10% since their last stored NAV (max {MAX_BIG_MOVE_SHARE:.0%})"))
    add = newer[["scheme_code", "date", "nav"]].copy()
    info = dict(newest_date=str(newest), to_add=len(add), already_stored=len(same) - len(conflict), older_than_stored=older,
                conflicts=conflict[["scheme_code", "date", "nav", "nav_old"]].astype(str).to_dict("records")[:20],
                big_moves=newer[move > 0.10][["scheme_code", "nav_old", "nav"]].astype(str).to_dict("records")[:50],
                gaps_over_10_days=int(((newer.date - newer.date_old).dt.days > 10).sum()),
                new_direct_growth_schemes_seen=int(new[~new.scheme_code.isin(universe) & new.scheme_name.str.contains("direct", case=False)
                                                       & new.scheme_name.str.contains("growth", case=False)].scheme_code.nunique()))
    return G, add, info


def run(text: str, root: Path = ROOT, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    stored = pd.read_parquet(root / "nav_raw.parquet"); universe = set(pd.read_parquet(root / "schemes.parquet").scheme_code)
    new = parse(text)
    gates, add, info = check(text, new, stored, universe, today)
    ok = all(g.ok for g in gates)
    report = dict(run_at=dt.datetime.now().isoformat(timespec="seconds"), ok=ok, gates=[asdict(g) for g in gates], **info)
    if ok and len(add):
        merged = pd.concat([stored, add], ignore_index=True).drop_duplicates(["scheme_code", "date"]).sort_values(["scheme_code", "date"]).reset_index(drop=True)
        tmp = root / "nav_raw.parquet.tmp"; merged.to_parquet(tmp, index=False)
        shutil.copy2(root / "nav_raw.parquet", root / "nav_raw.parquet.bak")
        os.replace(tmp, root / "nav_raw.parquet")
        ev, ad = dq.run(merged)
        ev.to_parquet(root / "dq_events.parquet", index=False); ad.to_parquet(root / "dq_adjustments.parquet", index=False)
        report["written"] = dict(rows_added=len(add), total_rows=len(merged), dq_events=len(ev), dq_adjustments=len(ad))
        from .manifest import write as write_manifest
        write_manifest(root, f"refresh from {URL}, newest NAV {info['newest_date']}")
    else:
        report["written"] = None
    rd = root / "refresh_reports"; rd.mkdir(exist_ok=True)
    (rd / f"{today.isoformat()}_{dt.datetime.now():%H%M%S}.json").write_text(json.dumps(report, indent=1, default=str))
    return report


def fetch(url: str = URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "imap/0.1 (personal research)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def main():
    text = fetch()
    raw = ROOT / "raw"; raw.mkdir(exist_ok=True)
    (raw / f"NAVAll_{dt.datetime.now():%Y%m%d_%H%M%S}.txt").write_text(text, encoding="utf-8")
    r = run(text)
    for g in r["gates"]:
        print(("PASS " if g["ok"] else "FAIL ") + g["name"].ljust(20) + g["detail"])
    status = "LOADED" if r["written"] else ("UP TO DATE (all checks passed; no new NAVs since the last load)" if r["ok"] else "NOT LOADED (a check failed; nothing written)")
    print(status, r["written"] or "", f"| new rows {r['to_add']}, conflicts {len(r['conflicts'])}, gaps>10d {r['gaps_over_10_days']}")
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
