"""Data manifest: SHA-256 and row counts of the data files the app trusts, plus where they came from.

refresh.py rewrites it after a successful load; App() verifies it at start and refuses to serve answers if a
file was changed outside the pipeline (partial copy, manual edit, OneDrive conflict copy, disk error).
"""
from __future__ import annotations
import datetime as dt, hashlib, json
from pathlib import Path

FILES = ("nav_raw.parquet", "schemes.parquet", "dq_events.parquet", "dq_adjustments.parquet", "renames.csv", "glossary.json",
         "macro/metals_monthly.parquet", "macro/usd_inr_daily.parquet", "macro/report.json", "macro_notes.csv", "macro/tbill_91d.parquet")
NAME = "MANIFEST.json"


class ManifestError(RuntimeError):
    pass


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(root: Path, source: str) -> dict:
    m = dict(written_at=dt.datetime.now().isoformat(timespec="seconds"), source=source,
             files={f: dict(sha256=_sha(root / f), bytes=(root / f).stat().st_size) for f in FILES if (root / f).exists()})
    (root / NAME).write_text(json.dumps(m, indent=1))
    return m


def verify(root: Path) -> dict:
    p = root / NAME
    if not p.exists():
        raise ManifestError(f"{NAME} is missing in {root}; run: python -m imap.manifest")
    m = json.loads(p.read_text())
    bad = [f for f, x in m["files"].items() if not (root / f).exists() or _sha(root / f) != x["sha256"]]
    missing = [f for f in FILES if f not in m["files"] and (root / f).exists()]
    if bad or missing:
        raise ManifestError(f"data files changed outside the pipeline: {bad + missing}. Restore them, or re-run "
                            f"the refresh, or (if the change was intended) re-write the manifest: python -m imap.manifest")
    return m


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[2] / "data"
    print(json.dumps(write(root, sys.argv[1] if len(sys.argv) > 1 else "manual: python -m imap.manifest"), indent=1))
