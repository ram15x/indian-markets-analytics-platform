"""Runs WITHOUT the real data: everything here uses the synthetic demo data built on the fly.
This is what GitHub CI can exercise (the real data is not published), so it covers the engines' agreement,
the withhold rules, the server routes and the shared-window comparison on a dataset anyone can rebuild."""
import json, sys, threading, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pandas as pd
import pytest
from imap import demo
from imap.app import App
from imap.planners import RulePlanner
from imap.server import make_handler, LocalServer

FUND = "DEMO Flexi Cap Fund - Direct Plan - Growth"
SMALL = "DEMO Small Cap Fund - Direct Plan - Growth"


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    return demo.build(tmp_path_factory.mktemp("demo"))


@pytest.fixture(scope="module")
def app(root): return App(RulePlanner(), root=root)


@pytest.fixture(scope="module")
def base(app):
    srv = LocalServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown(); srv.server_close()


def post(base, path, body):
    r = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json", "X-IMAP-Client": "1"})
    try:
        with urllib.request.urlopen(r) as x: return x.status, json.load(x)
    except urllib.error.HTTPError as e: return e.code, json.load(e)


def test_demo_data_is_deterministic_and_clearly_fake(tmp_path, root):
    other = demo.build(tmp_path / "again")
    for f in ("nav_raw.parquet", "schemes.parquet", "macro/usd_inr_daily.parquet", "macro/metals_monthly.parquet", "macro/tbill_91d.parquet"):
        pd.testing.assert_frame_equal(pd.read_parquet(root / f), pd.read_parquet(other / f))
    s = pd.read_parquet(root / "schemes.parquet")
    assert s.scheme_name.str.startswith("DEMO ").all() and (s.scheme_code >= 900000).all()
    assert demo.is_demo(json.loads((root / "MANIFEST.json").read_text())) and not demo.is_demo({"source": "AMFI"})


def test_answers_on_demo_data(app):
    t, _ = app.ask(f"3 year CAGR of {SMALL}")
    assert "CAGR" in t and "DEMO Small Cap" in t and "Withheld" not in t
    t, _ = app.ask(f"SIP of Rs 5000 in {FUND} for 5 years")
    assert "60 instalments totalling Rs 3,00,000" in t and "XIRR" in t
    t, _ = app.ask("5 year volatility of DEMO New Fund - Direct Plan - Growth")
    assert t.startswith("Withheld") and "2024-02-01" in t                # short history is refused, with the reason
    t, _ = app.ask("3 year total return of gold")
    assert "SYNTHETIC DEMO DATA" in t                                      # the series says what it is


def test_engines_agree_on_every_demo_series_and_window(app):
    """A (numpy) and B (DuckDB), and C (Rust) when built, must agree on every figure; any disagreement fails."""
    eng = app.engine; n_ok = 0; disagreements = []
    for code, s in eng.series.items():
        for years in (1, 3, 5):
            end = s.dates[-1]; start = (pd.Timestamp(end) - pd.DateOffset(years=years)).date()
            if pd.Timestamp(start) < pd.Timestamp(s.dates[0]):
                continue
            for metric in ("total_return", "cagr", "max_drawdown", "volatility", "sharpe", "sortino", "sip_xirr"):
                kw = dict(start=str(start), end=str(end), **(dict(amount=5000.0, day=5) if metric == "sip_xirr" else {}))
                r = eng.compute(metric, code, **kw)
                if r.status == "VERIFIED": n_ok += 1
                elif "disagree" in r.reason: disagreements.append((code, years, metric, r.reason))
    assert not disagreements, disagreements[:3]
    assert n_ok > 150                                                      # a real amount of work was checked, not skipped


def test_server_routes_on_demo(base):
    with urllib.request.urlopen(base + "/api/health") as x: h = json.load(x)
    assert h["ok"] and h["demo"] is True and h["schemes"] == 12
    html = urllib.request.urlopen(base + "/").read().decode()
    assert 'id="demobar"' in html and "invented" in html
    code, j = post(base, "/api/ask", {"question": f"3 year CAGR of {SMALL}"})
    assert code == 200 and j["status"] == "ANSWERED" and j["facts"][0]["code"] == 900003
    code, j = post(base, "/api/screen", {"text": "cap", "metric": "cagr", "years": 3, "top": 10})
    assert code == 200 and j["status"] == "OK" and j["verified"] >= 5 and j["not_updated"] == 0
    code, j = post(base, "/api/common", {"assets": ["gold", SMALL], "metric": "total_return", "years": 3})
    assert code == 200 and j["status"] == "ANSWERED" and j["window"]["end"] == "2026-04-01" and len(j["facts"]) == 2


def test_manifest_detects_a_tampered_demo_file(tmp_path):
    r = demo.build(tmp_path / "t")
    p = r / "nav_raw.parquet"; df = pd.read_parquet(p); df.loc[0, "nav"] = 1.0; df.to_parquet(p, index=False)
    from imap.manifest import ManifestError
    with pytest.raises(ManifestError):
        App(RulePlanner(), root=r)


def test_screen_has_peer_context_and_survivorship_note(base):
    code, j = post(base, "/api/screen", {"text": "cap", "metric": "cagr", "years": 3, "top": 3})
    assert code == 200 and j["status"] == "OK"
    n = j["verified"]; assert n >= 3 and len(j["all_rows"]) == n and len(j["rows"]) == 3
    vals = sorted(r["value"] for r in j["all_rows"])
    assert j["median"] == (vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2)
    assert j["rows"][0]["better_than_pct"] == 100 and j["all_rows"][-1]["better_than_pct"] == 0
    assert "survivorship" in j["survivorship"].lower() or "closed or merged" in j["survivorship"]


def test_learn_endpoint_and_numbers_behind_answer(base):
    with urllib.request.urlopen(base + "/api/learn") as x: j = json.load(x)
    assert j["topics"] and j["starters"]["new"] and "Not advice" in j["disclaimer"]
    code, a = post(base, "/api/ask", {"question": f"3 year CAGR of {SMALL}"})
    b = a["facts"][0]["behind"]
    assert "365" in b["formula"] and b["reading"] and {"start_nav", "end_nav", "days"} <= set(b["numbers"])
    assert b["numbers"]["days"] > 1000 and b["numbers"]["engines"].startswith("A+B")
