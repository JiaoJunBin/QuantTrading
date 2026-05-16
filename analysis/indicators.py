"""Volume / price indicators in pure pandas.

Inputs: a DataFrame with columns ``open``, ``high``, ``low``, ``close``, ``volume``
and a DatetimeIndex (any timezone, but expected to be regular intraday bars —
15-min in this project). Outputs are pd.Series aligned to the input index.

No LEAN dependency — usable in QuantBook research notebooks, plain Jupyter,
offline analysis, or unit tests.

Signal form note
----------------
Some indicators (OBV, ADL) are path-dependent cumulative sums whose raw values
grow unboundedly. Those are not directly comparable across time — use the
``*_zscore`` variants when feeding them to IC analysis. Bounded indicators
(MFI [0,100], CMF [-1,1]) are testable directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─── price-relative ──────────────────────────────────────────────────────────

def vwap(df: pd.DataFrame, reset: str = "D") -> pd.Series:
    """Cumulative volume-weighted average price, reset each ``reset`` period.

    Default ``reset='D'`` floors the index to calendar day — correct for US
    equity ET-based intraday data because 9:30–16:00 ET sits inside one UTC day.
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = tp * df["volume"]
    bucket = df.index.floor(reset)
    return pv.groupby(bucket).cumsum() / df["volume"].groupby(bucket).cumsum()


def vwap_deviation(df: pd.DataFrame) -> pd.Series:
    """Signed % distance of close from intraday VWAP. Negative = below VWAP."""
    v = vwap(df)
    return (df["close"] - v) / v


# ─── flow-of-funds ───────────────────────────────────────────────────────────

def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume (cumulative, path-dependent). Use ``obv_zscore`` for IC."""
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def obv_zscore(df: pd.DataFrame, window: int = 96) -> pd.Series:
    """OBV z-score over a rolling window (default 96 bars ≈ 1 trading day at 15m)."""
    o = obv(df)
    return (o - o.rolling(window).mean()) / o.rolling(window).std()


def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index, bounded [0, 100]."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    raw_mf = tp * df["volume"]
    tp_diff = tp.diff()
    pos_mf = raw_mf.where(tp_diff > 0, 0.0)
    neg_mf = raw_mf.where(tp_diff < 0, 0.0)
    pos_sum = pos_mf.rolling(period).sum()
    neg_sum = neg_mf.rolling(period).sum()
    # Avoid division by zero — when neg_sum=0, MFI=100 by convention.
    money_ratio = pos_sum / neg_sum.replace(0, np.nan)
    out = 100 - (100 / (1 + money_ratio))
    out = out.fillna(100.0).where(neg_sum > 0, 100.0)
    return out


def adl(df: pd.DataFrame) -> pd.Series:
    """Accumulation/Distribution Line (cumulative). Use ``adl_zscore`` for IC."""
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    return (mfm.fillna(0) * df["volume"]).cumsum()


def adl_zscore(df: pd.DataFrame, window: int = 96) -> pd.Series:
    a = adl(df)
    return (a - a.rolling(window).mean()) / a.rolling(window).std()


def cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Chaikin Money Flow, bounded [-1, 1]."""
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    mfv = (mfm.fillna(0) * df["volume"])
    return mfv.rolling(period).sum() / df["volume"].rolling(period).sum()


# ─── volume features ─────────────────────────────────────────────────────────

def volume_zscore(df: pd.DataFrame, window: int = 96) -> pd.Series:
    v = df["volume"]
    return (v - v.rolling(window).mean()) / v.rolling(window).std()


def volume_ratio(df: pd.DataFrame, window: int = 96) -> pd.Series:
    """Volume divided by its rolling mean. >1 = above average."""
    v = df["volume"]
    return v / v.rolling(window).mean()


# ─── batch compute helper ────────────────────────────────────────────────────

ALL = {
    "vwap_deviation": vwap_deviation,
    "obv_zscore":     obv_zscore,
    "adl_zscore":     adl_zscore,
    "mfi":            mfi,
    "cmf":            cmf,
    "volume_zscore":  volume_zscore,
    "volume_ratio":   volume_ratio,
}


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """Run every indicator in ``ALL`` against ``df``; return a wide DataFrame."""
    return pd.DataFrame({name: fn(df) for name, fn in ALL.items()}, index=df.index)
