"""Indicator implementations using numpy only."""
from __future__ import annotations

import numpy as np


def _rolling_window(arr: np.ndarray, window: int) -> np.ndarray:
    """Return 2-d view of the array with sliding window."""
    if window > arr.size:
        raise ValueError("window too large")
    shape = arr.shape[:-1] + (arr.shape[-1] - window + 1, window)
    strides = arr.strides + (arr.strides[-1],)
    return np.lib.stride_tricks.as_strided(arr, shape=shape, strides=strides)


# ----------------------------------------------------------------------
# Moving statistics
# ----------------------------------------------------------------------


def sma(arr: np.ndarray, window: int) -> np.ndarray:
    rw = _rolling_window(arr, window)
    res = np.empty_like(arr, dtype=float)
    res[: window - 1] = np.nan
    res[window - 1 :] = rw.mean(axis=1)
    return res


def std(arr: np.ndarray, window: int) -> np.ndarray:
    rw = _rolling_window(arr, window)
    res = np.empty_like(arr, dtype=float)
    res[: window - 1] = np.nan
    res[window - 1 :] = rw.std(axis=1, ddof=0)
    return res


# ----------------------------------------------------------------------
# Indicators
# ----------------------------------------------------------------------


def bollinger_bands(close: np.ndarray, window: int = 20, num_std: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ma = sma(close, window)
    sd = std(close, window)
    upper = ma + num_std * sd
    lower = ma - num_std * sd
    return lower, ma, upper


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    diff = np.diff(close, prepend=close[0])
    gain = np.clip(diff, 0, None)
    loss = -np.clip(diff, None, 0)
    avg_gain = np.empty_like(close, dtype=float)
    avg_loss = np.empty_like(close, dtype=float)

    avg_gain[:period] = np.nan
    avg_loss[:period] = np.nan

    avg_gain[period] = gain[1 : period + 1].mean()
    avg_loss[period] = loss[1 : period + 1].mean()

    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - 100 / (1 + rs)
    rsi[: period + 1] = np.nan
    return rsi


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))
    atr = np.empty_like(close, dtype=float)
    atr[:period] = np.nan
    atr[period] = tr[1 : period + 1].mean()
    for i in range(period + 1, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    plus_dm = np.maximum(high - np.roll(high, 1), 0)
    minus_dm = np.maximum(np.roll(low, 1) - low, 0)
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm <= plus_dm] = 0

    atr_val = atr(high, low, close, period)

    plus_di = 100 * np.divide(plus_dm, atr_val, where=~np.isnan(atr_val))
    minus_di = 100 * np.divide(minus_dm, atr_val, where=~np.isnan(atr_val))
    dx = 100 * np.divide(np.abs(plus_di - minus_di), plus_di + minus_di + 1e-10, where=(plus_di + minus_di) != 0)

    adx = np.empty_like(close, dtype=float)
    adx[: 2 * period] = np.nan
    adx[2 * period] = np.nanmean(dx[period : 2 * period + 1])
    for i in range(2 * period + 1, len(close)):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return adx
