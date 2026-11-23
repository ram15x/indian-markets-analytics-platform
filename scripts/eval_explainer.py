"""Run the explainer once per model on the answered questions. Usage: eval_explainer.py [model]"""
import sys, json; from pathlib import Path
sys.exit("RETIRED: v1 test, already run once (docs/MODEL_RUN_1.md). Use the _v2 script.")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.app import App
from imap.planners import RulePlanner
from imap import execute, explain as X

model = sys.argv[1] if len(sys.argv) > 1 else "openai/gpt-oss-120b"
root = Path(__file__).parent.parent / "data"; outp = root / f"explain_eval_{model.replace('/', '_')}.json"
if outp.exists(): sys.exit(f"{outp.name} exists: one run per model")
app = App(RulePlanner()); W = X.ChatExplainer(model=model); rows = []
for e in json.load(open(root / "planner_eval.json")):
    if e["expect"] != "ANSWER": continue
    try: o = execute.run(app.planner.plan(e["q"]), app.resolver, app.engine)
    except Exception as ex: rows.append(dict(q=e["q"], skipped=str(ex))); continue
    if o.status != "ANSWERED": rows.append(dict(q=e["q"], skipped=o.status)); continue
    t = X.fact_table(o)
    try: raw = W.write(e["q"], t)
    except RuntimeError as ex: sys.exit(f"stopped, nothing saved: {ex}")
    ok, why = X.check(raw, t, app.resolver.amc_words)
    rows.append(dict(q=e["q"], accepted=ok, reason=why, raw=raw, filled=X.fill(raw, t) if ok else None))
acc = sum(1 for r in rows if r.get("accepted")); n = sum(1 for r in rows if "accepted" in r)
print(f"{model}: accepted {acc} of {n} explained cases ({len(rows) - n} skipped because the stand-in planner did not answer)")
for r in rows:
    if "accepted" in r: print("\n---", r["q"], "|", "ACCEPTED" if r["accepted"] else "REJECTED: " + r["reason"]); print(r["filled"] or r["raw"])
outp.write_text(json.dumps(dict(model=model, accepted=acc, n=n, rows=rows), indent=1))
print("\nNow read every ACCEPTED text above for misleading statements or implied advice (see docs/EXPLAIN_EVAL.md).")
