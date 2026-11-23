import sys, shutil, datetime as dt; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np, pandas as pd, pytest
from imap import refresh as R
from imap import manifest as M

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture()
def root(tmp_path):
    for f in M.FILES + (M.NAME,):
        if (DATA / f).exists():
            (tmp_path / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy(DATA / f, tmp_path / f)
    return tmp_path


def make_file(root, day: dt.date, move=1.001, drop_share=0.0, extra_rows=6000, header=R.HEADER_OLD, bump_codes=()):
    nav = pd.read_parquet(root / "nav_raw.parquet"); last = nav.sort_values("date").groupby("scheme_code").tail(1)
    sch = pd.read_parquet(root / "schemes.parquet").set_index("scheme_code").scheme_name
    rng = np.random.default_rng(0); lines = [header, "", "Open Ended Schemes(Equity Scheme - Large Cap Fund)", "", "Some Mutual Fund", ""]
    for _, r in last.iterrows():
        if rng.random() < drop_share: continue
        m = 3.0 if r.scheme_code in bump_codes else move
        lines.append(f"{r.scheme_code};INF000000000;-;{sch[r.scheme_code]};{r.nav * m:.4f};{day:%d-%b-%Y}")
    for k in range(extra_rows):                       # other plans in the real file (regular, IDCW ...)
        lines.append(f"{900000 + k};INF999;-;Other Fund - Regular Plan - IDCW;12.3456;{day:%d-%b-%Y}")
    return "\n".join(lines)


def last_day(root): return pd.read_parquet(root / "nav_raw.parquet").date.max().date()


def test_good_file_loads(root):
    d = last_day(root) + dt.timedelta(days=1); before = len(pd.read_parquet(root / "nav_raw.parquet"))
    r = R.run(make_file(root, d), root, today=d)
    assert r["ok"] and r["written"]["rows_added"] > 1500
    assert len(pd.read_parquet(root / "nav_raw.parquet")) == before + r["written"]["rows_added"]
    assert (root / "nav_raw.parquet.bak").exists() and list((root / "refresh_reports").glob("*.json"))
    from imap.manifest import verify; verify(root)            # manifest rewritten to match the new data


def test_rerun_same_file_adds_nothing(root):
    d = last_day(root) + dt.timedelta(days=1); t = make_file(root, d)
    R.run(t, root, today=d); r2 = R.run(t, root, today=d)
    assert r2["ok"] and r2["to_add"] == 0


@pytest.mark.parametrize("kw,gate", [
    (dict(header="Scheme Code;Something Else"), "header"),
    (dict(extra_rows=0, drop_share=0.0), "row_count"),
    (dict(drop_share=0.3), "universe_coverage"),
    (dict(move=1.5), "no_systemic_jumps"),
])
def test_bad_files_refused_and_nothing_written(root, kw, gate):
    d = last_day(root) + dt.timedelta(days=1); before = (root / "nav_raw.parquet").read_bytes()
    r = R.run(make_file(root, d, **kw), root, today=d)
    assert not r["ok"] and r["written"] is None
    assert gate in [g["name"] for g in r["gates"] if not g["ok"]]
    assert (root / "nav_raw.parquet").read_bytes() == before
    from imap.manifest import verify; verify(root)            # refused load leaves data and manifest consistent


def test_stale_file_refused(root):
    d = last_day(root) + dt.timedelta(days=1)
    r = R.run(make_file(root, d), root, today=d + dt.timedelta(days=30))
    assert not r["ok"] and "fresh_dates" in [g["name"] for g in r["gates"] if not g["ok"]]


def test_single_jump_loads_and_is_flagged_by_dq(root):
    d = last_day(root) + dt.timedelta(days=1)
    r = R.run(make_file(root, d, bump_codes={125497}), root, today=d)
    assert r["ok"] and any(str(x["scheme_code"]) == "125497" for x in r["big_moves"])
    ev = pd.read_parquet(root / "dq_events.parquet")
    assert ((ev.scheme_code == 125497) & (ev.date == pd.Timestamp(d))).any()


def test_parse_handles_na_and_sections():
    t = R.HEADER_OLD + "\n\nOpen Ended Schemes(Debt)\n\nX Mutual Fund\n\n1;A;-;Fund A;N.A.;20-Nov-2026\n2;B;-;Fund B;12.5;20-Nov-2026\nbad;line\n"
    df = R.parse(t)
    assert list(df.scheme_code) == [1, 2] and np.isnan(df.nav[0]) and df.nav[1] == 12.5


def test_parse_old_layout_still_supported():
    t = R.HEADER_OLD + "\n\nX Mutual Fund\n\n7;A;-;Fund A - Direct Plan - Growth;10.5;20-Nov-2026\n"
    df = R.parse(t)
    assert list(df.scheme_code) == [7] and df.nav[0] == 10.5 and df.scheme_name[0] == "Fund A - Direct Plan - Growth"


def test_parse_new_layout_rebuilds_full_name():
    t = R.HEADER_NEW + "\n \nOpen Ended Schemes(X)\n \n135762;INF846K01WO1;-;Axis Children's Fund;Direct Plan;Growth Option;31.6264;20-Nov-2026\n"
    df = R.parse(t)
    assert list(df.scheme_code) == [135762] and df.nav[0] == 31.6264
    assert df.scheme_name[0] == "Axis Children's Fund - Direct Plan - Growth Option"


def test_unknown_layout_parses_nothing():
    assert len(R.parse("Code;Name;NAV\n1;a;2\n")) == 0
