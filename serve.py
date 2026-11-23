"""Start the local web page from the project root:  python serve.py   (then open http://127.0.0.1:8765)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from imap.server import main  # noqa: E402

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
