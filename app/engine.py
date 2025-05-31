"""Single-symbol trading engine."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Deque, Dict, List

import numpy as np

from .exchange import Exchange
from .notifier import TelegramNotifier
from .strategy.mean_reversion import MeanReversionSignal
from .risk_guard import RiskGuard

logger = logging.getLogger(__name__)


class MeanReversionEngine:
    """Aggregates ticks into 1-min candles, runs strategy, sends orders."""

    def __init__(
        self,
        symbol: str,
        exchange: Exchange,
        notifier: TelegramNotifier,
        risk_guard: RiskGuard,
        settings: dict,
    ) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.notifier = notifier
        self.risk_guard = risk_guard
        self.settings = settings
        self.strategy = MeanReversionSignal()

        self.ticks: Deque[dict] = deque(maxlen=60)
        self.candles: List[np.ndarray] = []  # rows: [ts, open, high, low, close, volume]
        self.position: dict | None = None
        self.entry_price: float = 0.0

    # ----------------------------------------------------------
    # WebSocket tick handling
    # ----------------------------------------------------------

    def _on_trade(self, data: dict) -> None:
        for tr in data.get("data", []):
            self.ticks.append(tr)

    async def start(self) -> None:
        topic = f"publicTrade.{self.symbol}"
        await self.exchange.subscribe(topic, self._on_trade)
        logger.info("Subscribed to %s", topic)
        asyncio.create_task(self._run_loop())

    # ----------------------------------------------------------
    # Aggregation & strategy
    # ----------------------------------------------------------

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._build_candle()
                await self._evaluate()
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Engine error: %s", exc)
            await asyncio.sleep(1)

    async def _build_candle(self) -> None:
        if not self.ticks:
            return
        now = int(self.ticks[-1]["T"] // 1000)  # seconds
        minute = now - (now % 60)
        minute_ticks = [t for t in self.ticks if int(t["T"] // 1000) - (int(t["T"] // 1000) % 60) == minute]
        if not minute_ticks:
            return
        prices = np.array([float(t["p"]) for t in minute_ticks])
        vol = sum(float(t["v"]) for t in minute_ticks)
        candle = np.array([minute, prices[0], prices.max(), prices.min(), prices[-1], vol])
        if self.candles and self.candles[-1][0] == minute:
            self.candles[-1] = candle
        else:
            self.candles.append(candle)
        # Keep last 500 candles
        if len(self.candles) > 500:
            self.candles = self.candles[-500:]

    async def _evaluate(self) -> None:
        if len(self.candles) < 100:
            return
        candles_np = np.vstack(self.candles)
        signal = self.strategy.generate(candles_np)
        if signal == "none":
            if self.position:
                exit_, price = self.strategy.should_exit(
                    self.position["side"].lower(), candles_np, self.entry_price
                )
                if exit_:
                    await self._close_position(price)
            return

        # Entry
        if self.position is None and self.risk_guard.is_trading_allowed():
            await self._open_position(signal, candles_np)

    # ----------------------------------------------------------
    # Orders & risk
    # ----------------------------------------------------------

    async def _open_position(self, side: str, candles: np.ndarray) -> None:
        balance = await self.exchange.wallet_balance()
        close = candles[-1, 4]
        atr_val = self.strategy._indicators(candles)["atr"][-1]
        sl_price = self.strategy.initial_sl(side, atr_val, close)
        risk_per_trade = self.settings["risk_per_trade"]  # fraction, e.g. 0.01
        risk_usdt = balance * risk_per_trade
        qty = self._safe_qty_calc(risk_usdt, abs(close - sl_price), close)
        qty = round(qty, self.settings.get("qty_step", 0.001))
        if qty <= 0:
            logger.warning("Qty calculated as zero. Skipping")
            return
        if not self.risk_guard.allocate_risk(risk_usdt):
            logger.info("Risk allocation failed")
            return

        order = await self.exchange.create_order(
            symbol=self.symbol,
            side="Buy" if side == "long" else "Sell",
            order_type="Market",
            qty=qty,
            reduce_only=False,
            sl=sl_price,
        )
        self.position = {"side": side, "qty": qty, "order_id": order["result"]["orderId"]}
        self.entry_price = close
        await self.notifier.send(f"\ud83d\ude80 Open {side.upper()} {self.symbol} qty={qty} entry={close:.2f}")

    async def _close_position(self, price: float) -> None:
        if not self.position:
            return
        side = "Sell" if self.position["side"] == "long" else "Buy"
        await self.exchange.create_order(
            symbol=self.symbol,
            side=side,
            order_type="Market",
            qty=self.position["qty"],
            reduce_only=True,
        )
        pnl_pct = (price - self.entry_price) / self.entry_price * (1 if side == "Sell" else -1) * 100
        self.risk_guard.register_trade(pnl_pct, 0.0)
        await self.notifier.send(f"\u2705 Close {self.symbol} {pnl_pct:.2f} %")
        self.position = None

    # ----------------------------------------------------------

    def _safe_qty_calc(self, risk_usdt: float, stop_dist: float, price: float) -> float:
        if stop_dist == 0:
            return 0.0
        raw_qty = risk_usdt / stop_dist
        return raw_qty * self.settings.get("leverage", 10)
