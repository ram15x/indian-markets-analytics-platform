"""Tests that need the local data files (AMFI NAV archive, built series) are marked `data`. Where those files are
absent (CI on GitHub: the data is not published), they are skipped and the skip reason says so, rather than failing."""
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
NEEDS_DATA = {"test_charts", "test_contracts", "test_engine_c", "test_explain", "test_planner", "test_server",
              "test_manifest", "test_mcp", "test_refresh", "test_macro"}
HAVE_DATA = (DATA / "nav_raw.parquet").exists()


def pytest_configure(config):
    config.addinivalue_line("markers", "data: needs the local data files (not published)")


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="needs local data files in data/ (not published); run the pipeline locally")
    for it in items:
        if it.module.__name__.split(".")[-1] in NEEDS_DATA:
            it.add_marker(pytest.mark.data)
            if not HAVE_DATA:
                it.add_marker(skip)
