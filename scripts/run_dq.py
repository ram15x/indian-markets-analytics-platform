"""Run the data-quality layer on the loaded universe and write events + adjustments."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pandas as pd
from imap import dq
root = Path(__file__).parent.parent / "data"
nav = pd.read_parquet(root / "nav_raw.parquet")
ev, ad = dq.run(nav)
ev.to_parquet(root / "dq_events.parquet", index=False); ad.to_parquet(root / "dq_adjustments.parquet", index=False)
print(ev.groupby("kind").scheme_code.agg(["count", "nunique"]).to_string()); print(len(ad), "adjustments")
