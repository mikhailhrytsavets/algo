"""Daily & aggregate risk limits module."""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class RiskGuard:
    """Tracks PnL and position/risk counts to enforce limits."""

    def __init__(
        self,
        max_daily_drawdown: float,
        profit_lock: float,
        max_trades: int,
        max_positions: int,
        max_total_risk: float,
    ) -> None:
        self.max_daily_drawdown = max_daily_drawdown
        self.profit_lock = profit_lock
        self.max_trades = max_trades
        self.max_positions = max_positions
        self.max_total_risk = max_total_risk

        self.reset()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def reset(self) -> None:
        today = _dt.date.today()
        self._date = today
        self.trades = 0
        self.realized = 0.0
        self.unrealized_risk = 0.0
        logger.info("RiskGuard reset for %s", today)

    def _check_new_day(self) -> None:
        if _dt.date.today() != self._date:
            self.reset()

    def register_trade(self, pnl: float, risk_used: float) -> None:
        """Call after each position close. ``pnl`` may be negative."""
        self._check_new_day()
        self.realized += pnl
        self.trades += 1
        self.unrealized_risk = max(self.unrealized_risk - risk_used, 0.0)
        logger.debug("Trade registered. Realized=%.4f", self.realized)

    def allocate_risk(self, risk: float) -> bool:
        self._check_new_day()
        if (
            self.trades >= self.max_trades
            or self.unrealized_risk + risk > self.max_total_risk
        ):
            return False
        self.unrealized_risk += risk
        return True

    def is_trading_allowed(self) -> bool:
        self._check_new_day()
        if self.realized <= -abs(self.max_daily_drawdown):
            logger.warning("Daily drawdown exceeded: %.2f %%", self.realized)
            return False
        if self.realized >= self.profit_lock:
            logger.info("Profit-lock reached: %.2f %%", self.realized)
            return False
        return True
