"""List chat models available to your key (reads GROQ_API_KEY; prints model ids only)."""
import json, os, sys, urllib.request, urllib.error
key = os.environ.get("GROQ_API_KEY") or sys.exit("set GROQ_API_KEY first")
req = urllib.request.Request("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {key}", "User-Agent": "imap/0.1"})
try:
    data = json.load(urllib.request.urlopen(req, timeout=30))["data"]
except urllib.error.HTTPError as e:
    sys.exit(f"API error HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
for m in sorted(data, key=lambda m: m["id"]):
    if m.get("active", True):
        print(m["id"], "| context", m.get("context_window", "?"), "| owner", m.get("owned_by", "?"))
