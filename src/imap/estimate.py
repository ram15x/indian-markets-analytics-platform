"""MODEL ESTIMATE, NOT A VERIFIED FIGURE: a 21-trading-day volatility estimate from GARCH(1,1) with Student-t errors.

Why this exists and what it is not: Forecast Lab experiment 1 (docs/LAB_1_VOLATILITY.md) tested this method against simple
baselines under a rule written before the run. It passed that rule, so it may be shown, but only separately from the
two-engine verified figures: there is no second implementation to agree with, and a forecast cannot be checked against
a future that has not happened. The estimate says nothing about direction or returns.
"""
from __future__ import annotations
import numpy as np
from .series import Series

HORIZON = 21
MIN_RETURNS = 750            # about three years of trading days
MIN_ANNUAL_VOL = 0.08        # the Lab tested only funds above this (it left out debt and liquid funds)
EWMA_LAMBDA = 0.94
BACKTEST = ("In a pre-registered walk-forward test on 256 funds (2019 to 2026) this method had the best average score of six, "
            "but its lead over a simple moving estimate (EWMA) was small and not reliable month to month. "
            "See docs/LAB_1_VOLATILITY.md.")


class EstimateError(ValueError):
    pass


def avg_variance(omega: float, alpha: float, beta: float, next_var: float, h: int = HORIZON) -> float:
    """Mean of the expected daily variances over the next h days, given the variance for the first of them."""
    ph = min(alpha + beta, 0.9999)
    long_run = omega / (1 - ph)
    return long_run + (next_var - long_run) * (1 - ph ** h) / (h * (1 - ph))


def ewma_vol(r: np.ndarray, lam: float = EWMA_LAMBDA) -> float:
    v = float(np.var(r[:30]))
    for x in r:
        v = lam * v + (1 - lam) * float(x) ** 2
    return float(np.sqrt(252 * v))


def trailing_vol(r: np.ndarray, n: int = 21) -> float:
    return float(np.sqrt(252 * np.mean(np.square(r[-n:]))))


def vol_estimate(s: Series, h: int = HORIZON) -> dict:
    if s.kind != "fund":
        raise EstimateError("this estimate is only provided for mutual fund NAV series")
    r = np.diff(np.log(s.nav))
    if len(r) < MIN_RETURNS:
        raise EstimateError(f"needs at least {MIN_RETURNS} daily returns; this fund has {len(r)}")
    full = float(np.sqrt(252 * np.mean(np.square(r))))
    if full < MIN_ANNUAL_VOL:
        raise EstimateError("this fund's volatility is below 8% a year; the model was tested only on funds above that, so no estimate is given")
    try:
        from arch import arch_model
    except ImportError as e:
        raise EstimateError("the optional model package is not installed; run: pip install -r requirements-lab.txt") from e
    res = arch_model(r * 100, mean="zero", vol="garch", p=1, q=1, dist="t").fit(disp="off", show_warning=False)
    om, al, be = (float(res.params[k]) for k in ("omega", "alpha[1]", "beta[1]"))
    var = float(np.var(r[:30] * 100))
    for x in r * 100:                                   # filter the variance up to the last NAV
        var = om + al * x * x + be * var
    garch = float(np.sqrt(252 * avg_variance(om, al, be, var, h))) / 100
    return dict(status="ESTIMATE", horizon_days=h, garch=garch, ewma=ewma_vol(r), trailing_21=trailing_vol(r),
                persistence=al + be, fit_end=str(s.dates[-1]), n_returns=int(len(r)), backtest=BACKTEST,
                label="Model estimate, not verified. Says nothing about direction or returns.")
