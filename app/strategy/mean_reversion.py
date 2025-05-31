"""Mean-reversion strategy rules."""
from __future__ import annotations

import numpy as np

from ..indicators import adx, atr, bollinger_bands, rsi


class MeanReversionSignal:
    def __init__(
        self,
        window_bb: int = 20,
        num_std: float = 2.0,
        period_rsi: int = 14,
        period_atr: int = 14,
        period_adx: int = 14,
        atr_mult_trailing: float = 1.2,
        atr_mult_stop: float = 1.5,
    ) -> None:
        self.window_bb = window_bb
        self.num_std = num_std
        self.period_rsi = period_rsi
        self.period_atr = period_atr
        self.period_adx = period_adx
        self.atr_mult_trailing = atr_mult_trailing
        self.atr_mult_stop = atr_mult_stop

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------

    def _indicators(self, candles: np.ndarray) -> dict[str, np.ndarray]:
        close = candles[:, 3]
        high = candles[:, 1]
        low = candles[:, 2]
        lower, mid, upper = bollinger_bands(close, self.window_bb, self.num_std)
        return {
            "close": close,
            "lower": lower,
            "mid": mid,
            "upper": upper,
            "rsi": rsi(close, self.period_rsi),
            "adx": adx(high, low, close, self.period_adx),
            "atr": atr(high, low, close, self.period_atr),
        }

    # --------------------------------------------------------------
    # Public
    # --------------------------------------------------------------

    def generate(self, candles: np.ndarray) -> str:
        ind = self._indicators(candles)
        i = -1  # last bar
        if np.isnan(ind["mid"][i]):
            return "none"
        # Entry filters
        if ind["adx"][i] >= 25:
            return "none"
        if ind["close"][i] < ind["lower"][i] and ind["rsi"][i] < 30:
            return "long"
        if ind["close"][i] > ind["upper"][i] and ind["rsi"][i] > 70:
            return "short"
        return "none"

    def should_exit(self, side: str, candles: np.ndarray, entry_price: float) -> tuple[bool, float]:
        ind = self._indicators(candles)
        i = -1
        close = ind["close"][i]
        mid = ind["mid"][i]
        atr_val = ind["atr"][i]
        if np.isnan(mid) or np.isnan(atr_val):
            return False, 0.0
        # primary exit: touch mid
        if (side == "long" and close >= mid) or (side == "short" and close <= mid):
            return True, close
        # trailing stop
        trailing_dist = self.atr_mult_trailing * atr_val
        if side == "long" and close <= entry_price - trailing_dist:
            return True, close
        if side == "short" and close >= entry_price + trailing_dist:
            return True, close
        return False, 0.0

    def initial_sl(self, side: str, atr_val: float, entry_price: float) -> float:
        sl_dist = min(0.015 * entry_price, self.atr_mult_stop * atr_val)
        return entry_price - sl_dist if side == "long" else entry_price + sl_dist
