"""Read-only Groww client (local use only).

Only the GET endpoints in ALLOWED can be called. There is no code path to orders, smart orders or margin
changes, and a test scans this file to keep it that way. The access token is passed in per call and never
stored. Docs: https://groww.in/trade-api/docs/curl/portfolio (fields as documented on 2026-11-23).
"""
from __future__ import annotations
import json, urllib.request, urllib.error

BASE = "https://api.groww.in"
ALLOWED = frozenset({"/v1/holdings/user", "/v1/positions/user"})


class GrowwError(RuntimeError):
    pass


def _get(path: str, token: str, opener=urllib.request.urlopen) -> dict:
    if path not in ALLOWED:
        raise PermissionError(f"{path} is not an allowed read-only endpoint")
    if not token:
        raise GrowwError("no Groww access token")
    req = urllib.request.Request(BASE + path, method="GET", headers={
        "Accept": "application/json", "Authorization": f"Bearer {token}", "X-API-VERSION": "1.0", "User-Agent": "imap/0.1"})
    try:
        with opener(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise GrowwError(f"Groww API error HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}") from None
    except urllib.error.URLError as e:
        raise GrowwError(f"could not reach Groww: {e.reason}") from None
    if data.get("status") != "SUCCESS":
        raise GrowwError(f"Groww returned status {data.get('status')!r}")
    return data.get("payload") or {}


def holdings(token: str, opener=urllib.request.urlopen) -> list[dict]:
    """Stock holdings as documented: isin, trading_symbol, quantity, average_price (Rs), plus lock/pledge fields."""
    rows = _get("/v1/holdings/user", token, opener).get("holdings") or []
    out = []
    for h in rows:
        q = float(h.get("quantity") or 0); avg = float(h.get("average_price") or 0)
        out.append(dict(isin=str(h.get("isin") or ""), symbol=str(h.get("trading_symbol") or ""), quantity=q,
                        average_price=avg, cost=q * avg,
                        locked=float(h.get("demat_locked_quantity") or 0) + float(h.get("groww_locked_quantity") or 0),
                        pledged=float(h.get("pledge_quantity") or 0), t1=float(h.get("t1_quantity") or 0)))
    return out


def summary(rows: list[dict]) -> dict:
    """Cost-basis view only: no prices are available on the free plan, so no current value or P&L."""
    total = sum(r["cost"] for r in rows)
    rows = sorted(rows, key=lambda r: -r["cost"])
    for r in rows:
        r["share_of_cost"] = (r["cost"] / total) if total else 0.0
    return dict(rows=rows, total_cost=total, count=len(rows),
                limits="Cost basis only (quantity x average buy price). Current value and gains need a price source, "
                       "which the free Groww plan does not include. Mutual funds are not in this API.")
