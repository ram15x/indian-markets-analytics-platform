"""Fixed, versioned teaching text for the Learn layer. Written by the assistant on 2026-11-23, NOT yet reviewed by Ram.
Nothing here is generated at run time and none of it is advice: it explains how to read past figures.
The formulas describe what imap/metrics_a.py does; tests/test_learn.py checks every measure has an entry."""
from __future__ import annotations

LEARN_VERSION = "2026-11-23a"

FORMULA = dict(
    total_return="end NAV / start NAV - 1",
    cagr="(end NAV / start NAV) ^ (365 / days between the two dates) - 1",
    max_drawdown="the lowest value of (NAV / highest NAV so far - 1) inside the period",
    volatility="standard deviation of daily log returns x sqrt(252)",
    sip_xirr="the yearly rate r at which every instalment out and the final value in sum to zero when each is discounted by (1 + r) ^ (days / 365)",
    rolling_return="annualised return of every calendar window of the stated length that ends in the period; the headline value is the median, with min, max and share of negative windows alongside",
    sharpe="(mean daily excess return over the 91-day T-bill rate / its standard deviation) x sqrt(252)",
    sortino="like Sharpe, but divides by the downside deviation only (days below the risk-free rate)",
)

READING = dict(
    total_return="Rs 100 became Rs (100 + this number). It says nothing about how long that took, so only compare it between periods of the same length.",
    cagr="The steady yearly rate that gives the same end result. Real years were bumpy; this smooths them, so a 3-year CAGR of 15% does not mean any single year gave 15%.",
    max_drawdown="The worst fall from a peak to a later low in this period, before any recovery. If it says -30%, someone who bought at the peak saw Rs 100 become Rs 70 at the lowest point.",
    volatility="How much the daily NAV jumps around, scaled to a year. Higher means a bumpier ride. It is not the same as loss: a fund can be volatile and still go up.",
    sip_xirr="The yearly rate that matches what your monthly instalments grew to, taking into account that later instalments had less time to grow. Use this, not CAGR, for SIPs.",
    rolling_return="The typical (median) yearly return across every start date, plus the best, worst and how often it was negative. A wide gap between best and worst means the start date mattered a lot.",
    sharpe="Return above a safe rate per unit of bumpiness. Higher is better risk-adjusted past performance. It depends on the period chosen and is unreliable over short ones.",
    sortino="Like Sharpe but only counts the bad bumps. Read the same way: higher is better past performance per unit of downside.",
)

TOPICS = [
    dict(id="absolute-vs-cagr", level="new", title="Total return vs CAGR",
         text="Total return is the whole change over the period. CAGR is that change expressed per year, so a 3-year and a 7-year result can be compared. A fund that doubled in 7 years has a CAGR near 10.4%; one that doubled in 3 years is near 26%."),
    dict(id="nav", level="new", title="What NAV is",
         text="NAV (net asset value) is the price of one unit of a mutual fund: the value of everything the fund owns, minus costs, divided by the number of units. A higher NAV does not mean a fund is expensive or better; only its change over time carries information."),
    dict(id="direct-regular", level="new", title="Direct vs Regular plans",
         text="The same fund has two plans. Regular pays a commission to the distributor, so its yearly expenses are higher and its NAV grows a little slower. Direct has no commission. This project's data is Direct Growth plans only, so figures here will not match Regular-plan factsheets exactly."),
    dict(id="growth-idcw", level="new", title="Growth vs IDCW",
         text="In a Growth plan, earnings stay in the NAV. In an IDCW plan the fund pays money out and the NAV drops by that amount. Comparing NAV changes of an IDCW plan understates what the investor received. That is why only Growth plans are used."),
    dict(id="drawdown", level="new", title="Drawdown: the fall you would have lived through",
         text="Return numbers hide the ride. Maximum drawdown is the largest peak-to-low fall in the period. Before looking at a return, look at the drawdown and ask whether you could have stayed invested through it."),
    dict(id="sip-xirr", level="mid", title="SIP returns and XIRR",
         text="A SIP puts in money on many dates, so each rupee has had a different time to grow. XIRR finds the one yearly rate that explains all those dated cash flows. It will usually differ from the fund's CAGR over the same years because it depends on when the market rose or fell relative to your instalments."),
    dict(id="sharpe-sortino", level="mid", title="Sharpe and Sortino",
         text="Both divide excess return (over a risk-free rate, here the 91-day T-bill) by a measure of variability. Sharpe uses all variability; Sortino only the downside. They are sensitive to the period, to how returns are measured, and to the risk-free series, so differences between 0.7 and 0.8 mean very little."),
    dict(id="past-future", level="new", title="Past returns do not predict future returns",
         text="Every figure here describes what already happened. A fund that ranked first over 3 years has no more than an uncertain tendency to rank first over the next 3. Use past figures to understand a fund's behaviour (risk, consistency), not to forecast."),
    dict(id="start-date", level="mid", title="Why the start date changes everything",
         text="Trailing returns depend on the end date and window you pick. Ask for the same fund over 1, 3 and 5 years, and across different end dates, before drawing a conclusion. Rolling returns show how much it varies."),
    dict(id="survivorship", level="mid", title="Survivorship bias",
         text="Funds that performed badly are often merged into others or closed. A list of funds that exist today is therefore a list of survivors, and averages or rankings of survivors look better than what investors in the whole category got. This data contains only funds still running."),
    dict(id="categories", level="mid", title="Why peers must be like for like",
         text="Comparing a small-cap fund with a short-duration debt fund is meaningless: they take different risks. The screener groups funds by words in their names, which is only an approximation of the official SEBI categories."),
    dict(id="conventions", level="expert", title="Conventions used, and where they can differ",
         text="Annualisation uses actual days / 365 for periods of a year or more, matching fund houses' factsheets; volatility and Sharpe use 252 trading days; XIRR uses actual/365. Start dates use the last NAV on or before the date. Other apps use other conventions, so a few hundredths of a percent difference is normal."),
    dict(id="verification", level="expert", title="What 'verified' means here and what it does not",
         text="Two or three independently written implementations (numpy, DuckDB, optionally Rust) computed the figure and agreed to 1e-9 relative. That shows the arithmetic is consistent, not that the data or the definition is right. Data checks and external comparisons with fund-house documents are listed in docs/ENGINE_RESULTS.md, with their limits."),
]

STARTERS = dict(
    new=["What is the 3 year CAGR of SBI Small Cap?", "Max drawdown of Axis Bluechip since inception"],
    mid=["SIP of Rs 5000 on the 5th in quant small cap for 5 years, what XIRR?", "Compare 5 year volatility of SBI Small Cap vs Nippon India Small Cap"],
    expert=["5 year Sharpe ratio of Parag Parikh Flexi Cap", "5 year Sortino ratio of Nippon India Small Cap"],
)


def payload() -> dict:
    return dict(version=LEARN_VERSION, topics=TOPICS, starters=STARTERS, disclaimer="Education about how to read past figures. Not advice, not a recommendation, not a forecast.")
