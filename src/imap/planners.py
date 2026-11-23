"""Planners turn a question into a plan. Two kinds:
- RulePlanner: a scripted stand-in (regex), used for development and tests. Not a model.
- ChatPlanner: asks an OpenAI-compatible chat API (e.g. Groq) using the USER's key from the
  environment. Its output is only a plan, which plan.validate checks. UNTESTED until a key is used.
"""
from __future__ import annotations
import json, os, re, time, urllib.request, urllib.error

_METRIC_WORDS = [
    ("rolling_return", r"rolling"), ("sortino", r"sortino"), ("sharpe", r"sharpe"),
    ("sip_xirr", r"\bsip\b|\bxirr\b"), ("max_drawdown", r"drawdown|biggest fall|worst fall"),
    ("volatility", r"volatil|\brisk\b"), ("cagr", r"\bcagr\b|annuali[sz]ed|per year"),
    ("total_return", r"return|gain|grow"),
]


class RulePlanner:
    name = "rule-stand-in"

    def plan(self, q: str) -> dict:
        t = q.lower()
        metric = next((m for m, p in _METRIC_WORDS if re.search(p, t)), None)
        if metric is None:
            raise ValueError("stand-in planner: no metric word found")
        ym = re.search(r"(\d{1,2})\s*(?:-|\s)?\s*(?:y|yr|yrs|year|years)\b", t)
        years = int(ym.group(1)) if ym else ("inception" if re.search(r"inception|since start|ever", t) else 3)
        body = re.sub(r"\b(?:rs\.?|inr)\s*\d[\d,]*|₹\s*\d[\d,]*|\b\d[\d,]{2,}\s*(?:rs|inr|₹|a month|per month|monthly)\b|\bsip\s*(?:of|for|with)?\s*\d[\d,]{2,}|\b\d[\d,]{2,}\s*sip\b", " ", t)
        body = re.sub(r"\b\d{1,2}\s*(?:-|\s)?\s*(?:y|yr|yrs|year|years)\b", " ", body)
        body = re.sub(r"\bon (?:the )?\d{1,2}(?:st|nd|rd|th)?\b", " ", body)
        body = re.sub(r"\btotal returns?\b", " ", body)          # the measure, not part of a name like "Total Market"
        parts = re.split(r",|\bvs\.?|\bversus\b|\band\b|\bwith\b", body)
        drop = r"\b(what|whats|is|was|the|of|for|compare|between|how|much|did|in|last|over|past|since|inception|start|ever|" \
               r"sip|xirr|cagr|returns?|gain|grow\w*|max|maximum|drawdown|biggest|worst|fall|volatility|risk|annuali[sz]ed|per|" \
               r"year|monthly|a|month|i|if|invest\w*|would|my|give|me|show|tell|fund's|fund|rolling|sharpe|sortino|ratio)\b"
        parts = [re.sub(r"\s+", " ", re.sub(drop, " ", p)).strip(" ?.,") for p in parts]
        parts = [p for p in parts if len(p) >= 2]
        if not parts:
            raise ValueError("stand-in planner: no fund named")
        steps, mids = [], []
        for k, p in enumerate(parts[:8], 1):
            steps.append(dict(id=f"f{k}", op="resolve", query=p))
            m = dict(id=f"m{k}", op="metric", metric=metric, fund=f"f{k}", years=years)
            if metric == "sip_xirr":
                am = re.search(r"(?:\b(?:rs\.?|inr)|₹)\s*(\d[\d,]*)|\b(\d[\d,]{2,})\s*(?:rs|inr|₹|a month|per month|monthly)\b|\bsip\s*(?:of|for|with)?\s*(\d[\d,]{2,})|\b(\d[\d,]{2,})\s*sip\b", t)
                if am: m["amount"] = int(next(g for g in am.groups() if g).replace(",", ""))   # no amount written: leave it out; the engine states the assumed default
                dm = re.search(r"\bon (?:the )?(\d{1,2})(?:st|nd|rd|th)?\b", t)
                m["day"] = int(dm.group(1)) if dm else 1
            steps.append(m); mids.append(m["id"])
        if len(mids) >= 2:
            steps.append(dict(id="c1", op="compare", inputs=mids))
        return {"steps": steps}


SYSTEM = """You turn a question about Indian mutual funds, gold, silver or the US dollar in rupees into a JSON plan. Output ONLY JSON.
Schema: {"steps": [step, ...], "notice": optional} with at most 12 steps. Step types:
{"id": "f1", "op": "resolve", "query": "<fund name exactly as the user wrote it>"}
{"id": "m1", "op": "metric", "metric": one of total_return|cagr|max_drawdown|volatility|sip_xirr|rolling_return|sharpe|sortino,
 "fund": "<id of a resolve step>", "years": integer 1-20 or "inception",
 "amount": number (sip_xirr only, ONLY if the user wrote an amount), "day": 1-28 (sip_xirr only, ONLY if the user wrote a day)}
{"id": "c1", "op": "compare", "inputs": ["m1", "m2", ...]}   (same metric and years, 2+ funds)
{"id": "a1", "op": "ask", "about": "metric", "options": [2-5 metric names]}
Rules:
- Pick a metric only if the user's words name it: return/gain/how much -> total_return; annualised/CAGR/per year -> cagr;
  drawdown/fall/drop -> max_drawdown; volatility/volatile/swings -> volatility; SIP/XIRR -> sip_xirr;
  rolling returns -> rolling_return (years = the rolling window length, e.g. 3 for '3-year rolling returns').
- Sharpe ratio -> sharpe; Sortino ratio -> sortino. Use them only when the user names them. The code decides whether a figure
  can be computed, so still plan the metric even for gold, silver or the dollar; never refuse to plan it yourself.
- Gold, silver and the dollar-rupee exchange rate are valid subjects, like funds. Write a resolve step whose query is exactly
  "gold", "silver" or "USD/INR" (use "USD/INR" for dollar, rupee, exchange rate or forex wording), then the usual metric step.
  They can be compared with each other or with funds. A fund whose name contains "gold" or "silver" is a fund: keep its full name.
- Vague words such as risk, risky, safe, performance, performed, how good: use ONE "ask" step listing suitable metrics, no other steps.
- Years: use the number the user wrote; "since inception"/"since start" -> "inception"; if no period is written, use 3.
- Advice questions (should I, is it a good buy, which to pick): set "notice": "advice". Prediction questions (will it,
  next year, going to): set "notice": "prediction". Then add resolve+metric steps ONLY for funds the user named
  (cagr, 3 years unless a period is written), or no steps if no fund is named.
- Never write any result, number of return, or opinion."""


class ChatPlanner:
    """OpenAI-compatible chat API. Key read from the env var given (never stored, never logged)."""

    def __init__(self, base_url="https://api.groq.com/openai/v1", model="openai/gpt-oss-120b", key_env="GROQ_API_KEY", key=None):
        self.base_url, self.model, self.key_env, self._key = base_url.rstrip("/"), model, key_env, key
        self.name = f"chat:{model}"

    def plan(self, q: str) -> dict:
        key = self._key or os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"no key: paste one on the page or set {self.key_env}")
        body = json.dumps(dict(model=self.model, temperature=0, response_format={"type": "json_object"},
                               messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}])).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", body,
                                     {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "imap/0.1"})
        for attempt in range(8):
            try:
                r = urllib.request.urlopen(req, timeout=120); break
            except urllib.error.HTTPError as e:
                msg = e.read()[:400].decode("utf-8", "replace")
                if e.code == 429 and attempt < 7:      # rate limit: wait as told, then retry the same request
                    m = re.search(r"try again in ([\d.]+)s", msg)
                    wait = float(m.group(1)) + 1.5 if m else 15.0
                    print(f"  rate limited, waiting {wait:.0f}s", flush=True); time.sleep(wait); continue
                raise RuntimeError(f"API error HTTP {e.code}: {msg[:300]}") from None
            except urllib.error.URLError as e:
                raise RuntimeError(f"could not reach {self.base_url}: {e.reason}") from None
        with r:
            txt = json.load(r)["choices"][0]["message"]["content"]
        return json.loads(txt)
