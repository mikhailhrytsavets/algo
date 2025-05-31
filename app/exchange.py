"""Bybit exchange interaction module (HTTP + WebSocket).
Only endpoints and topics required by the spec are implemented.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List

import aiohttp
from pybit.unified_trading import HTTP as BybitHTTP

# Constants
_WS_PUBLIC_ENDPOINT = "wss://stream.bybit.com/v5/public/linear"
_HTTP_ENDPOINT = "https://api.bybit.com"
_TESTNET_HTTP_ENDPOINT = "https://api-testnet.bybit.com"
_SYMBOL_SUFFIX = "USDT"

logger = logging.getLogger(__name__)


class Exchange:
    """Unified thin wrapper around Bybit HTTP & WebSocket v5."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._http = BybitHTTP(
            api_key=api_key,
            api_secret=api_secret,
            endpoint=_TESTNET_HTTP_ENDPOINT if testnet else _HTTP_ENDPOINT,
        )
        self._session = session or aiohttp.ClientSession()
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._subscriptions: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._connect_lock = asyncio.Lock()

    # ---------------------------------------------------------------------
    # HTTP
    # ---------------------------------------------------------------------

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: float | None = None,
        reduce_only: bool = False,
        close_on_trigger: bool = False,
        tp: float | None = None,
        sl: float | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "timeInForce": "GTC",
            "reduceOnly": reduce_only,
            "closeOnTrigger": close_on_trigger,
            "leverage": "10",
        }
        if price is not None:
            params["price"] = str(price)
        if tp is not None:
            params["takeProfit"] = str(tp)
        if sl is not None:
            params["stopLoss"] = str(sl)
        logger.debug("Create order params: %s", params)
        return self._http.post("/v5/order/create", params=params)

    async def cancel_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        params = {"category": "linear", "symbol": symbol, "orderId": order_id}
        return self._http.post("/v5/order/cancel", params=params)

    async def positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"category": "linear"}
        if symbol:
            params["symbol"] = symbol
        r = self._http.get("/v5/position/list", params=params)
        return r["result"]["list"]

    async def wallet_balance(self) -> float:
        r = self._http.get("/v5/account/wallet-balance", params={"accountType": "UNIFIED"})
        usdt = next((a for a in r["result"]["list"] if a["coin"] == _SYMBOL_SUFFIX), None)
        return float(usdt["availableBalance"]) if usdt else 0.0

    # ---------------------------------------------------------------------
    # WebSocket
    # ---------------------------------------------------------------------

    async def connect(self) -> None:
        async with self._connect_lock:
            if self._ws and not self._ws.closed:
                return
            self._ws = await self._session.ws_connect(_WS_PUBLIC_ENDPOINT, heartbeat=30)
            logger.info("WebSocket connected \u2192 %s", _WS_PUBLIC_ENDPOINT)
            # Resubscribe
            for topic in self._subscriptions:
                await self._send_ws({"op": "subscribe", "args": [topic]})
            asyncio.create_task(self._listen())

    async def _send_ws(self, msg: dict[str, Any]) -> None:
        assert self._ws is not None, "WebSocket not connected"
        await self._ws.send_str(json.dumps(msg))

    async def subscribe(self, topic: str, callback: Callable[[dict[str, Any]], None]) -> None:
        self._subscriptions.setdefault(topic, []).append(callback)
        await self.connect()
        await self._send_ws({"op": "subscribe", "args": [topic]})

    async def _listen(self) -> None:
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = msg.json(loads=json.loads)
                topic = data.get("topic")
                if topic and topic in self._subscriptions:
                    for cb in self._subscriptions[topic]:
                        cb(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("WS error %s", msg.data)
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                logger.warning("WS closed \u2192 reconnecting in 5s")
                await asyncio.sleep(5)
                await self.connect()
                break

    async def close(self) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
