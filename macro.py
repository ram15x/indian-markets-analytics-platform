"""Build gold, silver and USD/INR series from the RBI files in data/raw/rbi/. Run from the project folder: python macro.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from imap.macro import main
main()
