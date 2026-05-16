"""Daily-horizon indicators for Phase 2C IC analysis.

Designed for daily OHLCV DataFrames. Same conventions as `indicators.py`:
inputs are pandas DataFrames with `open`, `high`, `low`, `close`, `volume`
columns and a DatetimeIndex; outputs are pd.Series aligned to the index.

Why a separate module: a daily-horizon strategy has different relevant
features than an intraday one. VWAP doesn't apply (one bar per day); but
classic momentum (1m / 3m / 12m), moving-average distance, RSI, and
volatility-regime measures become relevant.
"""

import numpy as np
import pandas as pd


# ─── trend / momentum ────────────────────────────────────────────────────────

def momentum(close: pd.Series, lookback: int) -> pd.Series:
    """N-day total return: close[t] / close[t-N] - 1."""
    return close.pct_change(lookback)


def momentum_12_1(close: pd.Series) -> pd.Series:
    """Jegadeesh-Titman 12-1 momentum: 12-month return excluding the most recent
    month. Designed to capture trend while skipping short-term reversal noise.
    """
    return close.shift(21) / close.shift(252) - 1


def ma_distance(close: pd.Series, window: int) -> pd.Series:
    """Signed % distance of close from its N-day moving average."""
    ma = close.rolling(window).mean()
    return close / ma - 1


# ─── mean reversion ──────────────────────────────────────────────────────────

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI, bounded [0, 100]."""
    delta = close.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gain = gains.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0).where(avg_loss > 0, 100.0)


def zscore_price(close: pd.Series, window: int = 20) -> pd.Series:
    """Z-score of close vs its N-day rolling mean. Mean-reversion proxy."""
    ma = close.rolling(window).mean()
    sd = close.rolling(window).std()
    return (close - ma) / sd


# ─── money flow ──────────────────────────────────────────────────────────────

def obv(df: pd.DataFrame) -> pd.Series:
    """Cumulative On-Balance Volume. Path-dependent — use ``obv_z`` for IC."""
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def obv_z(df: pd.DataFrame, window: int = 60) -> pd.Series:
    o = obv(df)
    return (o - o.rolling(window).mean()) / o.rolling(window).std()


def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index, bounded [0, 100]. Same formula as intraday version."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    raw_mf = tp * df["volume"]
    tp_diff = tp.diff()
    pos_mf = raw_mf.where(tp_diff > 0, 0.0)
    neg_mf = raw_mf.where(tp_diff < 0, 0.0)
    pos_sum = pos_mf.rolling(period).sum()
    neg_sum = neg_mf.rolling(period).sum()
    money_ratio = pos_sum / neg_sum.replace(0, np.nan)
    out = 100 - 100 / (1 + money_ratio)
    return out.fillna(100.0).where(neg_sum > 0, 100.0)


def cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Chaikin Money Flow, bounded [-1, 1]."""
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    mfv = (mfm.fillna(0) * df["volume"])
    return mfv.rolling(period).sum() / df["volume"].rolling(period).sum()


# ─── volume / volatility ─────────────────────────────────────────────────────

def volume_z(volume: pd.Series, window: int = 20) -> pd.Series:
    return (volume - volume.rolling(window).mean()) / volume.rolling(window).std()


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    """Annualized realized vol over rolling window of daily returns."""
    return close.pct_change().rolling(window).std() * np.sqrt(252)


def atr_z(df: pd.DataFrame, period: int = 14, window: int = 60) -> pd.Series:
    """ATR z-score over a rolling window — captures volatility regime."""
    prev_close = df["close"].shift()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return (atr - atr.rolling(window).mean()) / atr.rolling(window).std()


# ─── batch compute ───────────────────────────────────────────────────────────

ALL = {
    "mom_5d":       lambda df: momentum(df["close"], 5),
    "mom_21d":      lambda df: momentum(df["close"], 21),
    "mom_63d":      lambda df: momentum(df["close"], 63),
    "mom_12_1":     lambda df: momentum_12_1(df["close"]),
    "ma_dist_50":   lambda df: ma_distance(df["close"], 50),
    "ma_dist_200":  lambda df: ma_distance(df["close"], 200),
    "rsi_14":       lambda df: rsi(df["close"], 14),
    "zscore_20":    lambda df: zscore_price(df["close"], 20),
    "obv_z":        lambda df: obv_z(df, 60),
    "mfi_14":       lambda df: mfi(df, 14),
    "cmf_20":       lambda df: cmf(df, 20),
    "volume_z":     lambda df: volume_z(df["volume"], 20),
    "realized_vol": lambda df: realized_vol(df["close"], 20),
    "atr_z":        lambda df: atr_z(df, 14, 60),
}


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({name: fn(df) for name, fn in ALL.items()}, index=df.index)
