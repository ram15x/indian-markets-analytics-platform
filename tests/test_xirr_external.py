"""XIRR against a worked example that comes from outside this project (Microsoft's XIRR documentation:
-10000 on 1 Jan 2008, then 2750, 4250, 3250, 2750; published result 0.373362535). Both solvers must reproduce it."""
from datetime import date
import numpy as np
import pytest
from imap.metrics_a import _xirr_newton
from imap.metrics_b import xirr_bisect

FLOWS = [(date(2008, 1, 1), -10000.0), (date(2008, 3, 1), 2750.0), (date(2008, 10, 30), 4250.0),
         (date(2009, 2, 15), 3250.0), (date(2009, 4, 1), 2750.0)]
PUBLISHED = 0.373362535

def test_newton_matches_published():
    days = np.array([(d - FLOWS[0][0]).days for d, _ in FLOWS], float); cf = np.array([c for _, c in FLOWS])
    assert _xirr_newton(days, cf) == pytest.approx(PUBLISHED, abs=1e-8)

def test_bisection_matches_published():
    assert xirr_bisect(FLOWS) == pytest.approx(PUBLISHED, abs=1e-8)

def test_single_lump_sum_is_cagr():
    # one outflow, one inflow 365 days apart: XIRR must equal the simple annual return
    f = [(date(2020, 1, 1), -100.0), (date(2020, 12, 31), 110.0)]
    assert xirr_bisect(f) == pytest.approx(0.10, abs=1e-9)
