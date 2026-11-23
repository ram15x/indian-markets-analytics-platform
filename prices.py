"""Load NSE's end-of-day closing prices (local, personal use):  python prices.py   (see docs/PRICES.md)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from imap.prices import main  # noqa: E402

if __name__ == "__main__":
    main()
