"""Telegram notifications."""
from __future__ import annotations

import asyncio
import logging

from telegram import Bot

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        # Ensure network I/O is run asynchronously
        self._loop = asyncio.get_event_loop()

    async def send(self, text: str) -> None:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Telegram send failed: %s", exc)
