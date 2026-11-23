"""Explanations of the measures come from a fixed, versioned glossary (data/glossary.json).

Why not model-written text: see docs/MODEL_RUN_2.md (the model's definitions were often wrong for this data).
Every figure, date and direction in an answer is written by code (answer.py); this adds definitions only.
"""
from __future__ import annotations
import json
from pathlib import Path
from .answer import render

GLOSSARY_FILE = Path(__file__).resolve().parents[2] / "data" / "glossary.json"
_G = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
GLOSSARY: dict[str, str] = _G["measures"]
GLOSSARY_VERSION: str = _G["version"]


def explain(outcome) -> str:
    """Answer text: code-written results, then the glossary entries for the measures used."""
    base = render(outcome)
    if outcome.status != "ANSWERED":
        return base
    metrics = list(dict.fromkeys(f["metric"] for f in outcome.facts))
    missing = [m for m in metrics if m not in GLOSSARY]
    if missing:
        raise KeyError(f"glossary has no entry for {missing}")
    lines = [f"What {'this measure means' if len(metrics) == 1 else 'these measures mean'} (glossary v{GLOSSARY_VERSION}):"]
    lines += [f"  - {GLOSSARY[m]}" for m in metrics]
    if any(f["code"] < 0 for f in outcome.facts):
        lines.append("  (For gold, silver and USD/INR, read NAV as the price or rate.)")
    return base + "\n\n" + "\n".join(lines)
