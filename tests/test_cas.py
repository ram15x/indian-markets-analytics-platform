import sys, json, datetime as dt; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap.portfolio import cas as C


def txn(d, typ, amount=None, units=None, nav=None):
    return {"date": d, "description": typ, "amount": amount, "units": units, "nav": nav, "balance": None, "type": typ}


def scheme(name, txns, close, nav, value, vdate="2024-01-01", open_=0, amfi="125497"):
    return {"scheme": name, "rta_code": "X", "rta": "CAMS", "isin": "INF000", "amfi": amfi, "open": open_, "close": close,
            "close_calculated": close, "valuation": {"date": vdate, "nav": nav, "value": value}, "transactions": txns}


def cas(*schemes, warnings=()):
    return {"statement_period": {"from": "01-Jan-2023", "to": "01-Jan-2024"}, "cas_type": "DETAILED", "file_type": "CAMS",
            "investor_info": {"name": "SECRET NAME", "email": "secret@example.com", "address": "SECRET ADDR", "mobile": "9999999999"},
            "parse_warnings": list(warnings),
            "folios": [{"folio": "1234567890", "amc": "SBI Mutual Fund", "PAN": "ABCDE1234F", "schemes": list(schemes)}]}


def test_one_buy_ten_percent_in_a_year():
    s = scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 1000, 11, 11000)
    r = C.analyse(cas(s)); x = r["schemes"][0]
    assert x["xirr_status"] == "VERIFIED" and x["xirr"] == pytest.approx(0.10, abs=1e-9) and x["invested_net"] == 10000
    assert r["portfolio"]["xirr"] == pytest.approx(0.10, abs=1e-9) and r["portfolio"]["value"] == 11000


def test_stamp_duty_and_redemption_with_stt_count_as_cash():
    t = [txn("2023-01-01", "PURCHASE", 9999.5, 999.95, 10), txn("2023-01-01", "STAMP_DUTY_TAX", 0.5),
         txn("2023-07-01", "REDEMPTION", -5000, -454.545, 11), txn("2023-07-01", "STT_TAX", 0.05)]
    s = scheme("B", t, 545.405, 12, 6544.86)
    x = C.analyse(cas(s))["schemes"][0]
    assert x["xirr_status"] == "VERIFIED" and x["invested_net"] == pytest.approx(10000 - 5000)
    # hand check: flows -10000 (Jan 1), +4999.95 (Jul 1), +6544.86 (Jan 1 next year)
    from imap.metrics_b import xirr_bisect
    want = xirr_bisect([(dt.date(2023, 1, 1), -10000.0), (dt.date(2023, 7, 1), 4999.95), (dt.date(2024, 1, 1), 6544.86)])
    assert x["xirr"] == pytest.approx(want, abs=1e-9)


def test_sign_quirk_does_not_flip_direction():
    s1 = scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 1000, 11, 11000)
    s2 = scheme("A", [txn("2023-01-01", "PURCHASE", -10000, -1000, 10)], 1000, 11, 11000)   # signs printed oddly
    assert C.analyse(cas(s1))["schemes"][0]["xirr"] == C.analyse(cas(s2))["schemes"][0]["xirr"]


def test_units_mismatch_withholds():
    s = scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 900, 11, 9900)
    x = C.analyse(cas(s))["schemes"][0]
    assert x["xirr_status"] == "WITHHELD" and any("differ from the closing balance" in c for c in x["checks"])


def test_value_mismatch_withholds():
    s = scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 1000, 11, 15000)
    x = C.analyse(cas(s))["schemes"][0]
    assert x["xirr_status"] == "WITHHELD" and any("differs from the printed value" in c for c in x["checks"])


def test_opening_balance_withholds():
    s = scheme("A", [txn("2023-06-01", "PURCHASE", 1000, 100, 10)], 600, 11, 6600, open_=500)
    x = C.analyse(cas(s))["schemes"][0]
    assert x["xirr_status"] == "WITHHELD" and any("bought before its period" in c for c in x["checks"])


def test_gift_withholds_and_is_left_out_of_portfolio():
    good = scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 1000, 11, 11000)
    gift = scheme("G", [txn("2023-01-01", "GIFT_IN", None, 100, None)], 100, 11, 1100)
    r = C.analyse(cas(good, gift))
    assert r["schemes"][1]["xirr_status"] == "WITHHELD" and "G" in r["portfolio"]["note"]
    assert r["portfolio"]["xirr"] == pytest.approx(0.10, abs=1e-9) and r["portfolio"]["value"] == 12100


def test_no_personal_details_in_output_and_folio_masked():
    r = C.analyse(cas(scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 1000, 11, 11000), warnings=["w1"]))
    blob = json.dumps(r)
    for secret in ("SECRET NAME", "secret@example.com", "SECRET ADDR", "9999999999", "ABCDE1234F", "1234567890"):
        assert secret not in blob
    assert r["schemes"][0]["folio"].endswith("7890") and r["parser_warnings"] == ["w1"]


def test_summary_statement_refused():
    c = cas(scheme("A", [], 0, 10, 0)); c["cas_type"] = "SUMMARY"
    with pytest.raises(ValueError, match="DETAILED"):
        C.analyse(c)


def test_casparser_model_input_is_accepted():
    from casparser.types import CASData
    m = CASData.model_validate(cas(scheme("A", [txn("2023-01-01", "PURCHASE", 10000, 1000, 10)], 1000, 11, 11000)))
    assert C.analyse(m)["schemes"][0]["xirr"] == pytest.approx(0.10, abs=1e-9)
