"""Information-Coefficient analysis for indicator validation.

Pure pandas / numpy / scipy. No LEAN dependency — can run in a QuantConnect
research notebook (after `qb.history(...)` produces a DataFrame) or against
any locally cached price/volume data.

Conventions
-----------
- `indicator` and `returns` are aligned pd.Series indexed by bar timestamp.
- "Forward returns" are computed inside the helpers via `.shift(-n)`; callers
  pass per-bar returns, not multi-period returns, to avoid double-shifting.
- All correlations are Spearman (rank) by default — robust to indicator scale
  and outliers, matches institutional IC convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class ICResult:
    """One forward-period IC measurement."""

    period: int
    ic: float
    pvalue: float
    n: int

    @property
    def significant(self) -> bool:
        return self.pvalue < 0.05 and not np.isnan(self.ic)

    def __str__(self) -> str:
        stars = "***" if self.pvalue < 0.01 else ("**" if self.pvalue < 0.05 else "")
        return f"IC_{self.period}={self.ic:+.4f} (p={self.pvalue:.4g}, n={self.n}) {stars}".rstrip()


def compute_ic(
    indicator: pd.Series,
    returns: pd.Series,
    periods: Iterable[int] = (1, 5, 20),
) -> dict[int, ICResult]:
    """Spearman IC between `indicator` and forward returns at each period.

    `returns` is the per-bar return series. For each `n` in `periods` we
    compare `indicator[t]` against the cumulative return over `t+1..t+n`.
    """
    out: dict[int, ICResult] = {}
    for n in periods:
        future = _forward_return(returns, n)
        df = pd.concat([indicator.rename("ind"), future.rename("fr")], axis=1).dropna()
        if len(df) < 30:
            out[n] = ICResult(n, float("nan"), 1.0, len(df))
            continue
        corr, pval = stats.spearmanr(df["ind"], df["fr"])
        out[n] = ICResult(n, float(corr), float(pval), len(df))
    return out


def rolling_ic(
    indicator: pd.Series,
    returns: pd.Series,
    window: int = 60,
    period: int = 1,
) -> pd.Series:
    """Rolling Pearson IC. Use for time-stability plots, not headline numbers.

    Pearson (not Spearman) because pandas `rolling.corr` doesn't ship Spearman;
    on rank-stable indicators the two agree closely.
    """
    future = _forward_return(returns, period)
    return indicator.rolling(window).corr(future)


def quantile_test(
    indicator: pd.Series,
    returns: pd.Series,
    n_quantiles: int = 5,
    period: int = 1,
) -> pd.DataFrame:
    """Bucket indicator into quantiles, return forward-return stats per bucket.

    A monotonic mean-return progression across buckets is the visual signature
    of a real factor. Flat or U-shaped means the IC, if any, is non-monotonic.
    """
    future = _forward_return(returns, period)
    df = pd.concat([indicator.rename("ind"), future.rename("fr")], axis=1).dropna()
    df["q"] = pd.qcut(df["ind"], n_quantiles, labels=False, duplicates="drop")
    grouped = df.groupby("q")["fr"]
    out = pd.DataFrame({
        "mean": grouped.mean(),
        "std": grouped.std(),
        "count": grouped.count(),
    })
    out["t_stat"] = out["mean"] / (out["std"] / np.sqrt(out["count"]))
    # Long-Short proxy: top bucket minus bottom bucket
    out.attrs["long_short_spread"] = float(out["mean"].iloc[-1] - out["mean"].iloc[0])
    return out


def ic_verdict(ic: float) -> str:
    """Categorize |IC| per the project's research_plan.md criteria."""
    a = abs(ic)
    if np.isnan(ic):
        return "n/a"
    if a < 0.02:
        return "reject"
    if a < 0.05:
        return "marginal"
    if a < 0.10:
        return "good"
    return "strong (check overfit)"


def ic_summary(
    indicator: pd.Series,
    returns: pd.Series,
    periods: Iterable[int] = (1, 5, 20),
) -> pd.DataFrame:
    """One-row-per-period summary table suitable for reports."""
    results = compute_ic(indicator, returns, periods)
    return pd.DataFrame(
        {
            "ic": [r.ic for r in results.values()],
            "pvalue": [r.pvalue for r in results.values()],
            "n": [r.n for r in results.values()],
            "verdict": [ic_verdict(r.ic) for r in results.values()],
        },
        index=[f"{p}-bar" for p in results],
    )


def _forward_return(per_bar_returns: pd.Series, n: int) -> pd.Series:
    """Cumulative forward return over the next `n` bars."""
    if n == 1:
        return per_bar_returns.shift(-1)
    return (1 + per_bar_returns).rolling(n).apply(np.prod, raw=True).shift(-n) - 1
