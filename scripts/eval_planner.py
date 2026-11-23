"""Score a planner on data/planner_eval.json. Usage: eval_planner.py rule|chat [model]
A chat run reads the key from the user's environment and writes data/planner_eval_<name>.json once."""
import sys, json; from pathlib import Path
sys.exit("RETIRED: v1 test, already run once (docs/MODEL_RUN_1.md). Use the _v2 script.")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.app import App
from imap.planners import RulePlanner, ChatPlanner
from imap.plan import PlanError
from imap import execute

root = Path(__file__).parent.parent / "data"
kind = sys.argv[1]
planner = RulePlanner() if kind == "rule" else ChatPlanner(model=sys.argv[2]) if len(sys.argv) > 2 else ChatPlanner()
outp = root / f"planner_eval_{planner.name.replace(':', '_').replace('/', '_')}.json"
if kind != "rule" and outp.exists(): sys.exit(f"{outp.name} exists: one run per model")
app = App(planner); E = json.load(open(root / "planner_eval.json")); rows = []
for e in E:
    try:
        plan = planner.plan(e["q"]); o = execute.run(plan, app.resolver, app.engine); got = o.status
    except (PlanError, ValueError, RuntimeError, KeyError) as ex:
        if isinstance(ex, RuntimeError): sys.exit(f"stopped, nothing saved: {ex}")
        o = None; got = "NOPLAN"; plan = None
    facts = sorted(tuple([f["code"], f["metric"], f["years"]] + ([int(f["detail"]["invested"] / f["detail"]["n"]), f["detail"].get("day", None)] if f["metric"] == "sip_xirr" else []))
                   for f in (o.facts if o and got == "ANSWERED" else []))
    want = sorted(tuple(f) for f in e.get("facts", []))
    if got == "ANSWERED":
        # SIP day is not returned by the engine detail; compare it from the plan instead
        if any(f[1] == "sip_xirr" for f in want):
            days = {s["fund"]: s.get("day", 1) for s in plan["steps"] if s["op"] == "metric"}
            facts = sorted(tuple(list(f[:4]) + [list(days.values())[i]]) if f[1] == "sip_xirr" else f for i, f in enumerate(facts))
        same = facts == want and (bool(o.ranking) == bool(e.get("compare")))
        verdict = "CORRECT" if (e["expect"] == "ANSWER" and same) else "WRONG_ANSWER"
    else:
        exp = {"CLARIFY": "CLARIFY", "WITHHELD": "WITHHELD"}.get(e["expect"])
        verdict = "CORRECT" if (got == exp or (e["expect"] == "NOFACT" and got in ("NOPLAN", "CLARIFY", "WITHHELD"))) else "SAFE_MISS"
    rows.append(dict(q=e["q"], expect=e["expect"], got=got, verdict=verdict, facts=facts, want=want))
summ = {v: sum(r["verdict"] == v for r in rows) for v in ("CORRECT", "WRONG_ANSWER", "SAFE_MISS")}
print(planner.name, summ)
for r in rows:
    if r["verdict"] != "CORRECT": print(" ", r["verdict"], "|", r["q"], "| got", r["got"], r["facts"], "| want", r["want"])
outp.write_text(json.dumps(dict(planner=planner.name, summary=summ, rows=rows), indent=1, default=str))
