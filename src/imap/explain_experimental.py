"""EXPERIMENTAL, NOT USED BY THE APP. Model-written explanations failed their test (docs/MODEL_RUN_2.md):
3 of 16 accepted, and several definitions were factually wrong. Kept only for the record and its tests.
"""
from __future__ import annotations
import json, os, re, time, urllib.request, urllib.error
from .answer import LABEL, render
from .explain import GLOSSARY

ADVICE = re.compile(r"\b(should|recommend\w*|advis\w*|buy|sell|switch|hold|avoid|best|worst|ideal|suitable|"
                    r"will|expect\w*|likely|predict\w*|forecast\w*|outlook|future|guarantee\w*|safe|"
                    r"good|bad|great|poor|attractive)\b", re.I)
SPECIFIC = re.compile(r"\b(first|second|third|former|latter|both|either|neither|"
                      r"(?:the|this|that|these|those|each|your|its|their)\s+(?:funds?|schemes?|ones?|investments?|portfolios?))\b", re.I)



def check(text: str, amc_words: frozenset = frozenset()) -> tuple[bool, str]:
    """The model's paragraph must be about the measures in general, with no figures and no fund references."""
    t = text.strip()
    if not t: return False, "empty"
    if len(t) > 1500: return False, "too long"
    if re.search(r"[{}]", t): return False, "placeholders are not used in v2"
    if re.search(r"\d", t): return False, "a digit appears"
    if re.search(r"[%₹$]|\brs\b|\binr\b|\bpercent\b|\blakh\b|\bcrore\b", t, re.I): return False, "a unit or currency appears"
    hit = [w for w in re.findall(r"[a-z&]+", t.lower()) if w in amc_words]
    if hit: return False, f"fund house name: {hit[0]!r}"
    if (m := ADVICE.search(t)): return False, f"advice or prediction word: {m.group(0)!r}"
    if (m := SPECIFIC.search(t)): return False, f"refers to particular funds: {m.group(0)!r}"
    return True, "ok"


SYSTEM = """You explain investment measures to a non-expert in India, in warm, plain English.
You will be told which measures appear in an answer. Write ONE short paragraph (at most 120 words)
explaining what those measures mean in everyday terms and how to read them.
The exact figures are shown separately by the app, so:
- Do not write any digit, %, Rs, lakh or crore. Do not name any fund or fund house.
- Do not refer to the funds in the answer at all (no "the fund", "this fund", "both funds", "first", "second").
- Do not advise, predict or judge: never use should, buy, sell, hold, will, expect, likely, future, best,
  worst, good, bad, safe, suitable.
Plain text only."""


def build_prompt(question: str, metrics: list[str], compare: bool) -> str:
    return (f"Question asked: {question}\nMeasures in the answer: {', '.join(LABEL[m] for m in metrics)}\n"
            f"Several funds are listed side by side: {'yes' if compare else 'no'}")


class ChatExplainer:
    """OpenAI-compatible chat API; key from the user's environment."""
    def __init__(self, base_url="https://api.groq.com/openai/v1", model="openai/gpt-oss-120b", key_env="GROQ_API_KEY"):
        self.base_url, self.model, self.key_env = base_url.rstrip("/"), model, key_env

    def write(self, question: str, metrics: list, compare: bool) -> str:
        key = os.environ.get(self.key_env)
        if not key: raise RuntimeError(f"set {self.key_env} to use the explainer")
        body = json.dumps(dict(model=self.model, temperature=0, messages=[
            {"role": "system", "content": SYSTEM}, {"role": "user", "content": build_prompt(question, metrics, compare)}])).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "imap/0.1"})
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
            return json.load(r)["choices"][0]["message"]["content"]


def explain(question: str, outcome, writer, amc_words: frozenset = frozenset()) -> dict:
    """Returns {'text', 'explained', 'reason'}. Results are always the code-written sentences."""
    base = render(outcome)
    if outcome.status != "ANSWERED":
        return dict(text=base, explained=False, reason="nothing to explain")
    metrics = list(dict.fromkeys(f["metric"] for f in outcome.facts))
    glossary = "What these measures mean (standard glossary): " + " ".join(GLOSSARY[m] for m in metrics)
    if writer is None:
        return dict(text=base + "\n\n" + glossary, explained=False, reason="no explainer key")
    try:
        raw = writer.write(question, metrics, bool(outcome.ranking))
    except Exception as e:
        return dict(text=base + "\n\n" + glossary, explained=False, reason=f"explainer unavailable: {e}")
    ok, why = check(raw, amc_words)
    if not ok:
        return dict(text=base + "\n\n" + glossary, explained=False, reason=f"explanation discarded: {why}", raw=raw)
    return dict(text=base + "\n\nWhat these measures mean (written by the model you chose, checked by code): " + raw.strip(),
                explained=True, reason="ok", raw=raw)
