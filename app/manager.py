"""Runs multiple MeanReversionEngine instances respecting RiskGuard."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

from .engine import MeanReversionEngine
from .exchange import Exchange
from .notifier import TelegramNotifier
from .risk_guard import RiskGuard

logger = logging.getLogger(__name__)


class EngineManager:
    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self.exchange = Exchange(
            api_key=settings["bybit"]["api_key"],
            api_secret=settings["bybit"]["api_secret"],
            testnet=settings["bybit"].get("testnet", True),
        )
        self.notifier = TelegramNotifier(
            token=settings["telegram"]["bot_token"],
            chat_id=settings["telegram"]["chat_id"],
        )
        self.risk_guard = RiskGuard(
            max_daily_drawdown=settings["risk_guard"]["daily_drawdown"],
            profit_lock=settings["risk_guard"]["profit_lock"],
            max_trades=settings["risk_guard"]["max_trades"],
            max_positions=settings["risk_guard"]["max_positions"],
            max_total_risk=settings["risk_guard"]["max_total_risk"],
        )
        self.engines: List[MeanReversionEngine] = []

    async def start(self) -> None:
        for sym in self.settings["symbols"]:
            engine = MeanReversionEngine(
                symbol=sym,
                exchange=self.exchange,
                notifier=self.notifier,
                risk_guard=self.risk_guard,
                settings=self.settings["trading"],
            )
            self.engines.append(engine)
            await engine.start()
        logger.info("%d engines started", len(self.engines))
        while True:
            await asyncio.sleep(60)
