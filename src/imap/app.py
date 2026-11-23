"""Wiring: load data once, then ask(question) -> text."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from .series import build_all
from .metrics_b import EngineB
from .engine import Engine
from .resolve import Resolver
from .plan import PlanError
from . import execute, explain

ROOT = Path(__file__).resolve().parents[2] / "data"


class App:
    def __init__(self, planner, root: Path = ROOT, check_manifest: bool = True):
        if check_manifest:
            from .manifest import verify
            self.manifest = verify(root)
        from . import contracts as C           # content rules, after the manifest has proved the files are unchanged
        nav = C.check(C.NAV, pd.read_parquet(root / "nav_raw.parquet"))
        ev = C.check(C.EVENTS, pd.read_parquet(root / "dq_events.parquet"))
        ad = C.check(C.ADJ, pd.read_parquet(root / "dq_adjustments.parquet"))
        sch = C.check(C.SCHEMES, pd.read_parquet(root / "schemes.parquet"))
        from .macro import load_series
        mser, mrows = load_series(root)                     # gold, silver, USD/INR (empty until macro.py has built them)
        series = build_all(nav, ev, ad); series.update(mser)
        navb = pd.concat([nav[["scheme_code", "date", "nav"]], mrows.astype({"scheme_code": "int64"})], ignore_index=True) if len(mrows) else nav
        from . import metrics_c
        self.engine = Engine(series, EngineB(navb, ev, ad), metrics_c.EngineC(series) if metrics_c.AVAILABLE else None)
        from .macro import load_risk_free
        rf = load_risk_free(root)                            # RBI 91-day T-bill yields; Sharpe/Sortino withheld without them
        if rf is not None:
            self.engine.set_risk_free(rf)
        self.resolver = Resolver(sch.scheme_code, sch.scheme_name, pd.read_csv(root / "renames.csv"))
        self.planner = planner

    def ask(self, q: str) -> tuple[str, dict]:
        try:
            plan = self.planner.plan(q)
        except Exception as e:
            return f"Could not plan this question: {e}", {}
        try:
            o = execute.run(plan, self.resolver, self.engine, q)
        except PlanError as e:
            return f"Rejected plan: {e}", plan
        return explain.explain(o), plan
