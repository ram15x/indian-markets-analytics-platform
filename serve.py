"""Start the local web page from the project root:  python serve.py [port] [--demo]   (then open http://127.0.0.1:8765)

--demo runs on SYNTHETIC data (builds demo_data/ the first time), for anyone who does not have the real data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from imap.server import main  # noqa: E402

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8765
    if "--demo" in sys.argv:
        from imap import demo
        root = Path(__file__).resolve().parent / "demo_data"
        if not (root / "MANIFEST.json").exists():
            demo.build(root)
        main(port, root)
    else:
        main(port)
