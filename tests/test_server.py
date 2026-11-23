import sys, json, threading, urllib.request; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src")); sys.path.insert(0, str(Path(__file__).parent))
import pytest
from imap.app import App
from imap.planners import RulePlanner
from imap.server import make_handler, LocalServer


@pytest.fixture(scope="module")
def base():
    srv = LocalServer(("127.0.0.1", 0), make_handler(App(RulePlanner())))
    from tests_support import fake_groww_opener, fake_cas_reader; srv.groww_opener = fake_groww_opener; srv.cas_reader = fake_cas_reader
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown(); srv.server_close()


def post(base, path, body, headers=None):
    h = {"Content-Type": "application/json", "X-IMAP-Client": "1"}; h.update(headers or {})
    r = urllib.request.Request(base + path, json.dumps(body).encode(), h)
    try:
        with urllib.request.urlopen(r) as x: return x.status, json.load(x)
    except urllib.error.HTTPError as e: return e.code, json.load(e)


def test_page_served(base):
    html = urllib.request.urlopen(base + "/").read().decode()
    assert "Ask about a fund" in html and "localStorage" not in html and "sessionStorage" not in html


def test_answer_without_key(base):
    code, j = post(base, "/api/ask", {"question": "What is the 3 year CAGR of SBI Small Cap?"})
    assert code == 200 and j["status"] == "ANSWERED" and j["facts"][0]["code"] == 125497 and "scripted" in j["planner"]
    assert j["glossary"]["entries"][0]["metric"] == "cagr"


def test_clarify_then_pick(base):
    q = "3 year return of gold fund"
    _, j = post(base, "/api/ask", {"question": q})
    assert j["status"] == "CLARIFY"
    c = j["clarify"]["candidates"][1]["code"]
    _, j2 = post(base, "/api/ask", {"question": q, "picks": {j["clarify"]["query"]: c}})
    assert j2["status"] == "ANSWERED" and j2["facts"][0]["code"] == c


def test_bad_key_error_never_echoes_key(base):
    secret = "gsk_TESTSECRET_should_never_come_back"
    code, j = post(base, "/api/ask", {"question": "3 year cagr of sbi small cap", "key": secret})
    assert secret not in json.dumps(j)          # whatever happens (no network here, or 401), the key is not echoed


def test_bad_requests(base):
    assert post(base, "/api/ask", {"question": "x"})[0] == 400
    assert post(base, "/api/models", {})[0] == 400


def test_cross_site_requests_refused(base):
    q = {"question": "3 year cagr of sbi small cap"}
    assert post(base, "/api/ask", q, {"X-IMAP-Client": ""})[0] == 403            # plain cross-site POST
    assert post(base, "/api/ask", q, {"Origin": "https://evil.example"})[0] == 403
    assert post(base, "/api/ask", q, {"Host": "evil.example:8765"})[0] == 403    # DNS rebinding
    r = urllib.request.Request(base + "/api/ask", method="OPTIONS")
    try: urllib.request.urlopen(r); code = 200
    except urllib.error.HTTPError as e: code = e.code
    assert code == 403


def test_security_headers(base):
    h = urllib.request.urlopen(base + "/").headers
    assert h["X-Frame-Options"] == "DENY" and "frame-ancestors 'none'" in h["Content-Security-Policy"]


def test_holdings_endpoint_cost_only_and_token_not_echoed(base):
    code, j = post(base, "/api/holdings", {"groww_token": "gtok_SECRET"})
    assert code == 200 and j["count"] == 1 and j["rows"][0]["symbol"] == "INFY" and "Cost basis only" in j["limits"]
    assert "valuation" in j
    assert "gtok_SECRET" not in json.dumps(j)
    assert post(base, "/api/holdings", {})[0] == 400


def test_unexpected_error_is_a_plain_500(base, monkeypatch):
    import imap.execute as E
    def boom(*a, **k): raise ZeroDivisionError("secret detail")
    monkeypatch.setattr(E, "run", boom)
    code, j = post(base, "/api/ask", {"question": "3 year cagr of sbi small cap", "key": ""})
    assert code == 500 and "secret detail" not in json.dumps(j) and "internal error" in j["error"]


def test_cas_endpoint_reads_in_memory_and_never_echoes_password(base):
    import base64
    pdf = base64.b64encode(b"%PDF-1.7 fake").decode()
    code, j = post(base, "/api/cas", {"pdf_base64": pdf, "cas_password": "ABCDE1234F"})
    assert code == 200 and j["portfolio"]["xirr_status"] == "VERIFIED" and "ABCDE1234F" not in json.dumps(j)
    code, j = post(base, "/api/cas", {"pdf_base64": pdf, "cas_password": "WRONGPASS1"})
    assert code == 400 and "WRONGPASS1" not in json.dumps(j) and "password" in j["error"]
    assert post(base, "/api/cas", {"pdf_base64": base64.b64encode(b"not a pdf").decode(), "cas_password": "x"})[0] == 400
    assert post(base, "/api/cas", {"cas_password": "x"})[0] == 400
