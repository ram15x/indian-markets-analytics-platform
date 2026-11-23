"""Explainer v2 test (docs/PLANNER_EVAL_V2.md): 16 ANSWER questions built from expected facts.
Usage: eval_explainer_v2.py <model>. One run per model."""
import sys, json; from pathlib import Path
sys.exit("RETIRED: explainer v2 test already run once (docs/MODEL_RUN_2.md). Model-written explanations are not used.")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from imap.app import App
from imap.planners import RulePlanner
from imap import execute, explain_experimental as X
from imap.resolve import Resolution


class ByCode:
    """Test harness only: the explainer test must not depend on the resolver, so funds are given by scheme code."""
    def __init__(self, codes, names): self.n = {f"scheme {c}": (int(c), nm) for c, nm in zip(codes, names, strict=True)}
    def resolve(self, q):
        c, nm = self.n[q]; return Resolution("RESOLVED", c, [(c, nm, 1.0)], "given by code (test)")


model = sys.argv[1]; root = Path(__file__).parent.parent / "data"
outp = root / f"explain_v2_eval_{model.replace('/', '_')}.json"
if outp.exists(): sys.exit(f"{outp.name} exists: one run per model")
app = App(RulePlanner()); W = X.ChatExplainer(model=model); rows = []
BYCODE = ByCode(app.resolver.codes, app.resolver.names)
for e in json.load(open(root / "planner_eval_v2.json")):
    if e["expect"] != "ANSWER": continue
    steps, mids = [], []
    for k, f in enumerate(e["facts"], 1):
        code, metric, years = f[:3]
        steps.append({"id": f"f{k}", "op": "resolve", "query": f"scheme {code}"})
        m = {"id": f"m{k}", "op": "metric", "metric": metric, "fund": f"f{k}", "years": years}
        if metric == "sip_xirr": m.update(amount=f[3], day=f[4])
        steps.append(m); mids.append(m["id"])
    if e.get("compare"): steps.append({"id": "c1", "op": "compare", "inputs": mids})
    o = execute.run({"steps": steps}, BYCODE, app.engine)
    assert o.status == "ANSWERED", (e["q"], o.status)
    metrics = list(dict.fromkeys(f["metric"] for f in o.facts))
    try: raw = W.write(e["q"], metrics, bool(o.ranking))
    except RuntimeError as ex: sys.exit(f"stopped, nothing saved: {ex}")
    ok, why = X.check(raw, app.resolver.amc_words)
    rows.append(dict(q=e["q"], metrics=metrics, accepted=ok, reason=why, raw=raw))
    print(f"--- {e['q']} | {'ACCEPTED' if ok else 'REJECTED: ' + why}\n{raw.strip()}\n", flush=True)
acc = sum(r["accepted"] for r in rows)
print(f"{model}: accepted {acc} of {len(rows)} | bar: >= 13 of 16, then Ram reads every accepted paragraph")
outp.write_text(json.dumps(dict(model=model, accepted=acc, n=len(rows), rows=rows), indent=1))
