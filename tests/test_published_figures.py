"""External truth kept as a permanent regression test.
Source: HDFC AMC performance document dated 31 Oct 2025 (files.hdfcfund.com, ROSHI_JAIN-RP_15.pdf), Regular Plan
Growth. NAV rows near each window edge are stored in tests/fixtures_hdfc_published.csv (from the AMFI archive)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pandas as pd, pytest
from imap import metrics_a as A
from imap.metrics_b import EngineB
from imap.series import Series

NAV = pd.read_csv(Path(__file__).parent / "fixtures_hdfc_published.csv", parse_dates=["date"]).sort_values(["scheme_code", "date"])
EV = pd.DataFrame({"scheme_code": [], "kind": [], "date": pd.to_datetime([])})
ADJ = pd.DataFrame({"scheme_code": pd.Series([], dtype="int64"), "effective_date": pd.to_datetime([]), "factor": []})
END = "2025-10-31"
PUB = [(101979, "2024-10-31", 8.68), (101979, "2022-10-31", 21.33), (101979, "2020-10-30", 25.98), (101979, "2015-10-30", 14.44),
       (102760, "2024-10-31", 9.77), (102760, "2022-10-31", 21.66), (102760, "2020-10-30", 29.22), (102760, "2015-10-30", 14.90),
       (101762, "2024-10-31", 10.20), (101762, "2022-10-31", 22.10), (101762, "2020-10-30", 29.36), (101762, "2015-10-30", 16.44)]
B = EngineB(NAV, EV, ADJ)


@pytest.mark.parametrize("code,start,published", PUB)
def test_cagr_matches_hdfc_published(code, start, published):
    g = NAV[NAV.scheme_code == code]; s = Series(code, g.date.values.astype("datetime64[D]"), g.nav.values)
    a = A.cagr(s, start, END)["value"] * 100; b = B.cagr(code, start, END)["value"] * 100
    assert round(a, 2) == published and round(b, 2) == published
