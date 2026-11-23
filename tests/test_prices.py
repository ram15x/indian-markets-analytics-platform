import sys, io, zipfile, datetime as dt; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap import prices as P

UDIFF = "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,LastPric\n"
OLD = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"


def udiff(n=1200, day="2026-11-20", extra=""):
    rows = [f"{day},{day},CM,NSE,STK,{k},INE{k:07d}01,SYM{k},EQ,10,11,9,{100 + k % 50}.5,100" for k in range(n)]
    return (UDIFF + "\n".join(rows) + "\n" + extra).encode()


def zipped(b):
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f: f.writestr("BhavCopy_NSE_CM_0_0_0_20261120_F_0000.csv", b)
    return z.getvalue()


def test_udiff_zip_loads(tmp_path):
    r = P.load(zipped(udiff()), tmp_path, today=dt.date(2026, 11, 22))
    assert r["ok"] and r["written"]["trade_date"] == "2026-11-20" and (tmp_path / "prices" / "latest.parquet").exists()


def test_old_headers_load(tmp_path):
    rows = [f"SYM{k},EQ,10,11,9,{100 + k}.25,100,99,1,1,20-NOV-2026,1,INE{k:07d}01" for k in range(1200)]
    r = P.load(("\n".join([OLD.strip()] + rows)).encode(), tmp_path, today=dt.date(2026, 11, 22))
    assert r["ok"], r["gates"]


def test_unknown_headers_refused_with_headers_listed(tmp_path):
    r = P.load(b"A,B,C\n1,2,3\n", tmp_path, today=dt.date(2026, 11, 22))
    assert not r["ok"] and "headers in the file" in r["gates"][0]["detail"] and not (tmp_path / "prices").exists()


@pytest.mark.parametrize("kw,today,gate", [
    (dict(n=100), dt.date(2026, 11, 22), "row_count"),
    (dict(), dt.date(2026, 12, 30), "fresh"),
    (dict(extra="2026-11-19,2026-11-19,CM,NSE,STK,9,INE9,X,EQ,1,1,1,5,5\n"), dt.date(2026, 11, 22), "one_trade_date"),
    (dict(extra="2026-11-20,2026-11-20,CM,NSE,STK,9,INE000000001,DUP,EQ,1,1,1,5,5\n"), dt.date(2026, 11, 22), "one_eq_row_per_isin"),
])
def test_bad_files_refused(tmp_path, kw, today, gate):
    r = P.load(udiff(**kw), tmp_path, today=today)
    assert not r["ok"] and gate in [g["name"] for g in r["gates"] if not g["ok"]]


def test_value_holdings(tmp_path):
    P.load(udiff(), tmp_path, today=dt.date(2026, 11, 22)); prices = P.latest(tmp_path)
    rows = [dict(isin="INE000000501", symbol="SYM5", quantity=10, average_price=100.0, cost=1000.0),
            dict(isin="INEUNKNOWN", symbol="X", quantity=1, average_price=50.0, cost=50.0)]
    s = P.value_holdings(rows, prices)
    assert rows[0]["close"] == 105.5 and rows[0]["value"] == pytest.approx(1055) and rows[0]["gain"] == pytest.approx(55)
    assert rows[1]["value"] is None and s["priced"] == 1 and s["unpriced"] == 1 and s["total_gain_priced"] == pytest.approx(55)


def test_no_price_file_means_cost_only():
    assert P.value_holdings([], None)["price_date"] is None
