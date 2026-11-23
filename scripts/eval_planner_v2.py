"""Score a planner on data/planner_eval_v2.json (rules: docs/PLANNER_EVAL_V2.md).
Usage: eval_planner_v2.py rule | chat <model>. One chat run per model; results in data/."""
import sys, json; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.app import App
from imap.planners import RulePlanner, ChatPlanner
from imap.plan import PlanError
from imap import execute
from imap.scoring import score, fact_key

root = Path(__file__).parent.parent / "data"
planner = RulePlanner() if sys.argv[1] == "rule" else ChatPlanner(model=sys.argv[2])
outp = root / f"planner_v2_eval_{planner.name.replace(':', '_').replace('/', '_')}.json"
if sys.argv[1] != "rule" and outp.exists(): sys.exit(f"{outp.name} exists: one run per model")
app = App(planner); rows = []
for i, e in enumerate(json.load(open(root / "planner_eval_v2.json")), 1):
    plan = o = err = None
    try:
        plan = planner.plan(e["q"])
    except RuntimeError as ex:
        sys.exit(f"stopped, nothing saved: {ex}")
    except Exception as ex:
        err = f"planning failed: {ex}"
    if plan is not None:
        try: o = execute.run(plan, app.resolver, app.engine, e["q"])
        except (PlanError, KeyError, TypeError) as ex: err = f"plan rejected: {ex}"
    v = score(e, o, err)
    rows.append(dict(q=e["q"], expect=e["expect"], verdict=v, status=o.status if o else "NOPLAN", notice=getattr(o, "notice", None),
                     facts=[fact_key(f) for f in o.facts] if o else [], error=err, plan=plan))
    print(f"{i:2} {v:12} {e['expect']:8} -> {rows[-1]['status']:11} {e['q']}", flush=True)
summ = {k: sum(r["verdict"] == k for r in rows) for k in ("CORRECT", "WRONG_ANSWER", "SAFE_MISS")}
print(planner.name, summ, "| bars: WRONG_ANSWER <= 1, CORRECT >= 25")
for r in rows:
    if r["verdict"] != "CORRECT": print(" ", r["verdict"], "|", r["q"], "| got", r["status"], r["notice"], r["facts"], "|", r["error"] or "")
outp.write_text(json.dumps(dict(planner=planner.name, summary=summ, rows=rows), indent=1, default=str))
