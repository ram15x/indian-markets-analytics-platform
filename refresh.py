"""Run the AMFI refresh from the project root:  python refresh.py   (see docs/REFRESH.md)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from imap.refresh import main  # noqa: E402

if __name__ == "__main__":
    main()
