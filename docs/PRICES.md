# Stock prices for your holdings (local, personal use)

`python prices.py` (project root) downloads NSE's daily CM bhavcopy for the latest trading day (it tries up to
8 days back for weekends and holidays, waiting 2 s between tries), checks it, and keeps only the latest
closing prices in data/prices/latest.parquet. The Groww holdings panel then shows close, value and gain.

URL used: https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip
(SOURCED from a third-party catalogue, not from NSE's own page; UNVERIFIED until the first run).
Column names are UNVERIFIED: the parser accepts UDiFF names (ISIN, TckrSymb, SctySrs, ClsPric, TradDt) or
older names (ISIN, SYMBOL, SERIES, CLOSE, TIMESTAMP), and refuses the load listing the headers it found
if neither matches.

Checks: >= 1,000 rows; one trade date; trade date within 7 days; > 500 EQ rows, all closes positive; one EQ
row per ISIN. A refused file writes nothing.

Terms: NSE states that ownership of its data stays with NSE and restricts redistribution (FEASIBILITY.md).
This is for your own use on your machine. data/prices/ and data/raw/ must not be committed to a public repo.
Gain is against Groww's average buy price; it ignores charges, dividends and taxes. Prices are end of day, not live.
