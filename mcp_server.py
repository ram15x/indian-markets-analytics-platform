"""Start the MCP server (stdio). Run from the project folder: python mcp_server.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from imap.mcp_server import main
main()
