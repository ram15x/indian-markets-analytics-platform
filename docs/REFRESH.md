# Nightly refresh

Source: AMFI's official daily file https://www.amfiindia.com/spages/NAVAll.txt (latest NAV per scheme).
Code: src/imap/refresh.py. Tests: tests/test_refresh.py (good file loads; re-run adds nothing; bad header,
truncated file, missing schemes, market-wide jumps and stale files are refused with nothing written).

## Gates (thresholds set before any real run)
header matches; >= 5,000 scheme rows; no duplicate codes; >= 90% of our 1,772 schemes present; newest date
within 7 days and none in the future; <= 2% of our schemes with missing/non-positive NAV; <= 0.5% with the
same date as stored but a different NAV; <= 2% of updated schemes moving more than 10% since their last
stored NAV. Individual large moves still load and are flagged by the data-quality layer.

## Run once by hand (on your Windows machine; the assistant's shells cannot reach amfiindia.com)
    cd "C:\path\to\indian-markets-analytics-platform\src"
    python -m imap.refresh
It prints PASS/FAIL per gate and LOADED or NOT LOADED. Raw downloads go to data/raw/, reports to
data/refresh_reports/. The previous nav_raw.parquet is kept as nav_raw.parquet.bak.

## Schedule it (your decision; run this yourself in PowerShell)
    schtasks /Create /SC DAILY /ST 23:45 /TN "IMAP NAV refresh" /TR "cmd /c cd /d \"C:\path\to\indian-markets-analytics-platform\src\" && python -m imap.refresh >> ..\data\refresh_log.txt 2>&1"
AMFI publishes NAVs in the evening; 23:45 IST leaves margin. Remove with: schtasks /Delete /TN "IMAP NAV refresh"

## Real runs
- 2026-11-23, first run: REFUSED (header gate). AMFI had moved Plan and Option into their own columns (8 columns).
  The parser now reads either layout by header name; any other layout is still refused with the header shown.
- 2026-11-23, same file after the fix (run on a copy of the data): all 9 gates pass; 0 new rows because the archive
  already held these dates; all 1,772 latest NAVs identical to the archive.

## Known limits
- The file has only the latest NAV. Missed days become gaps (reported as gaps_over_10_days when long).
  AMFI's NAV history download (max 90 days per request) could back-fill; not built.
- New Direct+Growth schemes are counted in the report but not added to the universe automatically.
- AMFI says an older NAV format was discontinued; if the format changes again, the header and row-count
  gates refuse the load rather than loading less data.
- Not yet run against the real file (no access from the assistant's shells).
