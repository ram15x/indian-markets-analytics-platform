import sys, io, json, re; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap.portfolio import groww as G

SRC = (Path(__file__).parent.parent / "src" / "imap" / "portfolio" / "groww.py").read_text()

FIXTURE = {"status": "SUCCESS", "payload": {"holdings": [
    {"isin": "INE002A01018", "trading_symbol": "RELIANCE", "quantity": 10, "average_price": 2500.5, "pledge_quantity": 0,
     "demat_locked_quantity": 0, "groww_locked_quantity": 0, "repledge_quantity": 0, "t1_quantity": 0,
     "demat_free_quantity": 10, "corporate_action_additional_quantity": 0, "active_demat_transfer_quantity": 0},
    {"isin": "INE467B01029", "trading_symbol": "TCS", "quantity": 2, "average_price": 3500, "t1_quantity": 1}]}}


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def fake_opener(seen):
    def op(req, timeout=30):
        seen.append(req); return FakeResp(json.dumps(FIXTURE).encode())
    return op


def test_holdings_parsed_and_headers_sent():
    seen = []; rows = G.holdings("tok123", fake_opener(seen))
    assert [r["symbol"] for r in rows] == ["RELIANCE", "TCS"] and rows[0]["cost"] == pytest.approx(25005.0)
    r = seen[0]
    assert r.get_method() == "GET" and r.full_url.endswith("/v1/holdings/user")
    assert r.headers["Authorization"] == "Bearer tok123" and r.headers["X-api-version"] == "1.0"


def test_summary_is_cost_only():
    s = G.summary(G.holdings("t", fake_opener([])))
    assert s["total_cost"] == pytest.approx(25005 + 7000) and abs(sum(r["share_of_cost"] for r in s["rows"]) - 1) < 1e-12
    assert "Cost basis only" in s["limits"]


def test_non_allowlisted_path_refused():
    with pytest.raises(PermissionError):
        G._get("/v1/order/create", "t", fake_opener([]))


def test_source_has_no_order_or_write_calls():
    code = SRC.split('"""', 2)[2]                         # code after the module docstring
    assert not re.search(r"order|smart|margin|gtt|oco|cancel|modify", code, re.I)
    for word in ("/order", "/smart", "/margin", "POST", "PUT", "DELETE", "PATCH"):
        assert word not in code, word
    assert G.ALLOWED == {"/v1/holdings/user", "/v1/positions/user"}


def test_failure_status_raises():
    def op(req, timeout=30): return FakeResp(json.dumps({"status": "FAILURE"}).encode())
    with pytest.raises(G.GrowwError): G.holdings("t", op)
