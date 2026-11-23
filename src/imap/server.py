"""Local web page. Run: python -m imap.server  (then open http://127.0.0.1:8765)

Binds to 127.0.0.1 only. A pasted key is read from the request body, used for that one request, and
dropped: it is not written to disk, logs or the response.
"""
from __future__ import annotations
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, cast
from pathlib import Path
from .app import App
from .planners import RulePlanner, ChatPlanner
from .plan import PlanError
from . import execute
from .answer import LABEL, NOTICE, WARN, render, sentence
from .explain import GLOSSARY, GLOSSARY_VERSION

class LocalServer(ThreadingHTTPServer):
    """The HTTP server plus the two outside readers the handlers use (swapped for fakes in tests)."""
    groww_opener: Callable[..., Any]
    cas_reader: Callable[[bytes, str], dict]


PAGE = Path(__file__).parent / "web" / "index.html"
MAX_BODY = 20_000
MAX_CAS_BODY = 15_000_000   # base64 PDF


def outcome_json(o, planner_name: str, plan, series=None) -> dict:
    d = dict(status=o.status, planner=planner_name, plan=plan, notice=NOTICE.get(o.notice) if o.notice else None,
             warning=WARN, text=render(o))
    if o.status == "ANSWERED":
        d["facts"] = [dict(code=f["code"], fund=f["fund"], metric=f["metric"], label=LABEL[f["metric"]],
                           years=f["years"], value=f["value"], sentence=sentence(f), notes=f["notes"],
                           start=f["detail"].get("start_date"), end=f["detail"].get("end_date")) for f in o.facts]
        d["ranking"] = o.ranking
        metrics = list(dict.fromkeys(f["metric"] for f in o.facts))
        d["glossary"] = dict(version=GLOSSARY_VERSION, entries=[dict(metric=m, label=LABEL[m], text=GLOSSARY[m]) for m in metrics])
        if series is not None:
            from . import charts
            try:
                d["chart"] = charts.for_outcome(o, series)
            except ValueError:
                d["chart"] = None
    elif o.status == "CLARIFY":
        d["clarify"] = o.clarify
    elif o.status == "ASK":
        d["ask"] = [dict(metric=m, label=LABEL[m]) for m in o.ask]
    elif o.status == "WITHHELD":
        d["reason"] = o.reason
    return d


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        server_version = "imap-local"

        def log_message(self, fmt, *args):          # path and status only; never bodies
            sys.stderr.write(f"{time.strftime('%H:%M:%S')} {self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}\n")

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)

        def _json(self, code: int, obj):
            self._send(code, json.dumps(obj, default=str).encode(), "application/json")

        def handle_one_request(self):
            """Any unexpected error becomes a plain 500; details go to the console only (never the request body)."""
            try:
                super().handle_one_request()
            except Exception as e:                      # noqa: BLE001
                import traceback
                sys.stderr.write(f"{time.strftime('%H:%M:%S')} internal error: {type(e).__name__}\n{traceback.format_exc(limit=6)}")
                try:
                    self._json(500, dict(error="internal error; see the server console"))
                except Exception:
                    pass

        def do_GET(self):
            why = self._local_only()
            if why:
                return self._json(403, dict(error=f"refused: {why}"))
            if self.path in ("/", "/index.html"):
                return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/health":
                return self._json(200, dict(ok=True, schemes=len(app.resolver.codes)))
            self._json(404, dict(error="not found"))

        def _local_only(self) -> str | None:
            """Block requests that did not come from this page on this machine.
            Host must be localhost/127.0.0.1 (stops DNS-rebinding), Origin (if sent) must match, and POSTs must
            carry X-IMAP-Client, which a cross-site form or simple fetch cannot add without a CORS preflight
            that this server never approves."""
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                return "bad host"
            origin = self.headers.get("Origin")
            if origin and origin.split("://", 1)[-1].split(":")[0] not in ("127.0.0.1", "localhost"):
                return "bad origin"
            if self.command == "POST" and self.headers.get("X-IMAP-Client") != "1":
                return "missing client header"
            return None

        def do_OPTIONS(self):                       # never approve a CORS preflight
            self._json(403, dict(error="cross-origin requests are not allowed"))

        def do_POST(self):
            why = self._local_only()
            if why:
                return self._json(403, dict(error=f"refused: {why}"))
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > (MAX_CAS_BODY if self.path == "/api/cas" else MAX_BODY):
                return self._json(400, dict(error="empty or too large request"))
            try:
                req = json.loads(self.rfile.read(n))
            except json.JSONDecodeError:
                return self._json(400, dict(error="request is not JSON"))
            key = (req.pop("key", None) or "").strip() or None      # removed from req before anything else touches it
            gtoken = (req.pop("groww_token", None) or "").strip() or None
            cas_pw = req.pop("cas_password", None)
            if self.path == "/api/ask":
                return self._ask(req, key)
            if self.path == "/api/models":
                return self._models(key)
            if self.path == "/api/holdings":
                return self._holdings(gtoken)
            if self.path == "/api/cas":
                return self._cas(req.pop("pdf_base64", None), cas_pw)
            self._json(404, dict(error="not found"))

        def _ask(self, req, key):
            q = str(req.get("question") or "").strip()
            if not 3 <= len(q) <= 400:
                return self._json(400, dict(error="question must be 3 to 400 characters"))
            planner = ChatPlanner(model=str(req.get("model") or "openai/gpt-oss-120b"), key=key) if key else RulePlanner()
            name = planner.name if key else "scripted stand-in (no key: not a model)"
            try:
                plan = planner.plan(q)
            except RuntimeError as e:                               # API errors: message only, never the key
                return self._json(502, dict(error=str(e).replace(key or "\0", "[key]")))
            except Exception as e:
                return self._json(200, dict(status="NOPLAN", planner=name, error=f"could not plan this question: {e}", warning=WARN))
            try:
                o = execute.run(plan, app.resolver, app.engine, q, picks=req.get("picks"))
            except (PlanError, KeyError, TypeError) as e:
                return self._json(200, dict(status="NOPLAN", planner=name, plan=plan, error=f"the plan was rejected by code checks: {e}", warning=WARN))
            self._json(200, outcome_json(o, name, plan, app.engine.series))

        def _holdings(self, token):
            from .portfolio import groww
            if not token:
                return self._json(400, dict(error="paste a Groww access token first"))
            try:
                rows = groww.holdings(token, cast(LocalServer, self.server).groww_opener)
            except groww.GrowwError as e:
                return self._json(502, dict(error=str(e).replace(token, "[token]")))
            out = groww.summary(rows)
            from . import prices
            out["valuation"] = prices.value_holdings(out["rows"], prices.latest())
            self._json(200, out)

        def _cas(self, b64, password):
            import base64, binascii
            if not b64 or not password:
                return self._json(400, dict(error="choose the CAS PDF and type its password"))
            try:
                data = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError):
                return self._json(400, dict(error="the file could not be read"))
            if not data.startswith(b"%PDF"):
                return self._json(400, dict(error="that file is not a PDF"))
            try:
                result = cast(LocalServer, self.server).cas_reader(data, str(password))
            except ValueError as e:                                  # e.g. SUMMARY statement
                return self._json(400, dict(error=str(e)))
            except Exception as e:                                   # noqa: BLE001 - parser errors: wrong password, unknown layout
                msg = str(e).replace(str(password), "[password]")[:200]
                return self._json(400, dict(error=f"could not read the statement ({type(e).__name__}): {msg}. "
                                                  "Check the password (usually your PAN in capitals) and that it is a CAMS/KFintech DETAILED CAS."))
            finally:
                del data; password = None                            # drop references; nothing was written to disk
            self._json(200, result)

        def _models(self, key):
            if not key:
                return self._json(400, dict(error="paste a key first"))
            import urllib.request, urllib.error
            r = urllib.request.Request("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}", "User-Agent": "imap/0.1"})
            try:
                data = json.load(urllib.request.urlopen(r, timeout=30))["data"]
            except urllib.error.HTTPError as e:
                return self._json(502, dict(error=f"API error HTTP {e.code}"))
            except urllib.error.URLError as e:
                return self._json(502, dict(error=f"could not reach Groq: {e.reason}"))
            skip = ("whisper", "guard", "orpheus", "safeguard")
            self._json(200, dict(models=sorted(m["id"] for m in data if m.get("active", True) and not any(s in m["id"] for s in skip))))
    return H


def bind_address() -> str:
    """127.0.0.1 always, except inside the Docker image (IMAP_IN_CONTAINER=1), where the container's own interface
    must be used so Docker can forward the port. Publish it to the host's loopback only: -p 127.0.0.1:8765:8765.
    The Host/Origin checks still apply, so a request must still say it is for localhost."""
    import os
    return "0.0.0.0" if os.environ.get("IMAP_IN_CONTAINER") == "1" else "127.0.0.1"   # noqa: S104 - container only


def main(port: int = 8765):
    app = App(RulePlanner())
    srv = LocalServer((bind_address(), port), make_handler(app))
    import urllib.request; srv.groww_opener = urllib.request.urlopen   # read by handlers via the server object
    from .portfolio.cas import read_pdf; srv.cas_reader = read_pdf
    print(f"Open http://127.0.0.1:{port}  (local only; Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
