"""Register this project's MCP server with Claude Desktop (Windows).

Run from the project folder:  python add_to_claude_desktop.py
It finds every claude_desktop_config.json Claude Desktop might read (normal
install and Microsoft Store install), backs each one up, adds the
"indian-markets-verified" entry and keeps everything else untouched.
"""
import glob
import json
import os
import shutil
import sys

NAME = "indian-markets-verified"
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "mcp_server.py")

appdata = os.environ.get("APPDATA", "")
local = os.environ.get("LOCALAPPDATA", "")
candidates = []
if appdata:
    candidates.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
if local:
    candidates += glob.glob(os.path.join(
        local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude",
        "claude_desktop_config.json"))
    for pkg in glob.glob(os.path.join(local, "Packages", "Claude_*")):
        d = os.path.join(pkg, "LocalCache", "Roaming", "Claude")
        if os.path.isdir(d):
            candidates.append(os.path.join(d, "claude_desktop_config.json"))

seen, targets = set(), []
for c in candidates:
    if c not in seen:
        seen.add(c)
        targets.append(c)

if not os.path.exists(SERVER):
    sys.exit(f"mcp_server.py not found next to this script: {SERVER}")

done = 0
for path in targets:
    folder = os.path.dirname(path)
    exists = os.path.exists(path)
    if not exists and not os.path.isdir(folder):
        continue  # that install flavour is not present
    data = {}
    if exists:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as e:
            print(f"SKIP {path}: existing file is not valid JSON ({e})")
            continue
        shutil.copy2(path, path + ".bak")
    data.setdefault("mcpServers", {})[NAME] = {
        "command": sys.executable,
        "args": [SERVER],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"OK   {path}")
    done += 1

if not done:
    print("No Claude Desktop config folder found. Open Claude Desktop, go to "
          "Settings > Desktop app > Extensions > Edit config once, then rerun.")
else:
    print("Now fully quit Claude Desktop from the tray and reopen it.")
