# MCP server

`python mcp_server.py` starts a Model Context Protocol server over stdio, so an AI agent can call the verified engine as tools. Clients include Claude Desktop, Claude Code and any other MCP client.

The agent plans the work and this code does every calculation. Every figure is computed by engine A (numpy) and engine B (DuckDB SQL). A figure is returned only if both agree; otherwise the tool returns WITHHELD with the reason.

## Tools (all read-only)

| Tool | What it does |
|---|---|
| `find_fund(query)` | Looks up a fund name, or `gold`, `silver` or `usd inr`. Returns one code (RESOLVED) or up to 5 candidates (CLARIFY). |
| `compute(metric, codes, years, sip_amount?, sip_day?)` | Computes one measure for 1–8 codes and ranks them. A SIP needs the user's own amount; no amount is assumed. |
| `answer_question(question, plan)` | Runs a plan the agent wrote. The plan is checked against the question: the period and the SIP amount must be in the user's words. |

The server also offers three resources:
- `imap://plan-schema`: the plan format.
- `imap://glossary`: the fixed definitions of each measure.
- `imap://data-status`: the date ranges and the manifest.

## Guards (all tested in `tests/test_mcp.py`)

- **No changes, no outside contact:** no tool writes files, reaches the network or calls Groww. A source scan in the tests enforces this.
- **Checked data only:** the data manifest is verified before the first answer, and tampered data stops the server.
- **Comparisons must cover the same period:** a comparison is withheld if the start or end dates differ by more than 7 days. For example, gold, whose data ends Apr 2026, is not ranked against a fund whose data ends Nov 2026.
- **Not every measure fits every series:** monthly gold and silver have no volatility or SIP. For USD/INR, any period that crosses the 2018–2022 gap is withheld.

## Claude Desktop

Add this to `claude_desktop_config.json`, adjusting the paths to your machine:

```json
{
  "mcpServers": {
    "indian-markets-verified": {
      "command": "python",
      "args": ["C:\\path\\to\\indian-markets-analytics-platform\\mcp_server.py"]
    }
  }
}
```

## Status

- **Tested:** the tools in-process, plus a real stdio round trip in the sandbox, using `mcp` 2.3.0.
- **Tried 2026-11-23, Claude Desktop (Microsoft Store install) on Windows:** the server connected, and the question "3 year CAGR of SBI Small Cap" in a new chat called the tool instead of web search. It answered 10.89% a year (20 Nov 2023 to 20 Nov 2026, NAV 153.99 to 210.02), matching the platform's own figure. `python add_to_claude_desktop.py` writes the config entry, including for the Store install, whose config lives under `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude`. One run on one machine.
