import io, json


class _R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def fake_groww_opener(req, timeout=30):
    assert req.get_method() == "GET"
    return _R(json.dumps({"status": "SUCCESS", "payload": {"holdings": [
        {"isin": "INE009A01021", "trading_symbol": "INFY", "quantity": 5, "average_price": 1500}]}}).encode())


def fake_cas_reader(data: bytes, password: str):
    from imap.portfolio import cas
    if password != "ABCDE1234F":
        raise RuntimeError(f"Incorrect password {password}")           # parser-style error that contains the password
    c = {"statement_period": {"from": "01-Jan-2023", "to": "01-Jan-2024"}, "cas_type": "DETAILED", "file_type": "CAMS",
         "investor_info": {"name": "N", "email": "e", "address": "a", "mobile": "m"}, "parse_warnings": [],
         "folios": [{"folio": "1234567890", "amc": "SBI Mutual Fund", "schemes": [{"scheme": "SBI Small Cap Fund - Direct Plan - Growth",
            "rta_code": "X", "rta": "CAMS", "isin": "INF200K01T28", "amfi": "125497", "open": 0, "close": 1000, "close_calculated": 1000,
            "valuation": {"date": "2024-01-01", "nav": 11, "value": 11000},
            "transactions": [{"date": "2023-01-01", "description": "p", "amount": 10000, "units": 1000, "nav": 10, "balance": 1000, "type": "PURCHASE"}]}]}]}
    return cas.analyse(c)
