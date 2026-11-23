# Indian Markets Analytics Platform: plan

Status: planning. No git repository yet; push to GitHub when finished.

## What it is
Ask questions in plain English over Indian market data. Every number is checked by code against
stored data before it is shown, or the answer is withheld. Same grounding approach as
AI Grounded Analytics Platform.

## Decisions (2026-11-22)
- Universe: NSE 500 stocks and indices; mutual funds (all schemes if storage allows, otherwise a
  chosen subset); gold and silver in INR.
- Audience: showcase plus personal use.
- Explainer: explains the verified numbers in detail; does NOT recommend buying or selling.
  Advice-type questions get a clear warning and an explanation, not a directive. (Not legal advice:
  check SEBI rules before publishing.)
- Bring-your-own-key, as before. Keys are never stored and never pasted into chat.
- Free tools only, no card.

## Open risks (unverified)
- NSE / Yahoo data terms for public display. Default: public site covers funds, gold and silver;
  stock questions stay local unless NSE's policy clearly allows display.
- Splits and bonus issues need adjusted prices.
- Growth vs dividend (IDCW) and direct vs regular fund plans must not be mixed.
- Neon free tier is 1 GB: all-scheme history may not fit.
- The cloud workspace cannot reach AMFI / NSE; downloads go through this computer.

## Phases
1. Feasibility spike: sample funds, Nifty 50 history, RBI gold series; read NSE data policy.
2. Warehouse and metrics: returns, CAGR, volatility, drawdown, SIP returns.
3. Verifier extensions and pre-registered dev/locked evals.
4. UI, tryout, hosting (Vercel + Neon), daily refresh via GitHub Actions.


## Requested by Ram (2026-11-23): tracking graphs, in the UI phase  [funds: BUILT 2026-11-23, see STATUS.md]
- Charts from the same verified data: NAV history (adjusted), drawdown from peak, rolling returns,
  SIP value vs amount invested, and side-by-side comparison. Each chart marks excluded dates and flagged moves.
- "Live" for mutual funds means daily: a fund has one NAV per business day, published in the evening.
  Charts update after the nightly refresh; there is no intraday fund data to show.
- Stocks, live (requested by Ram): LOCAL ONLY, through a broker API on Ram's own account (personal licence; never on
  the public site). Free option per third-party summaries (Oct 2026): Angel One SmartAPI, incl. live WebSocket and
  historical data (UNVERIFIED against SmartAPI's own docs). Zerodha's free Personal plan has no live data.
  Rules: market-data endpoints only (a test forbids order endpoints); Ram logs in himself (no password/TOTP
  handling by the assistant); historical stock charts only after split/bonus adjustment is verified.
