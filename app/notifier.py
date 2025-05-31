"""Telegram notifications."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

try:
    from telegram import Bot  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    class Bot:
        """Fallback bot when python-telegram-bot is missing."""

        def __init__(self, *_, **__):
            logger.warning(
                "python-telegram-bot not installed; Telegram notifications disabled"
            )

        async def send_message(self, chat_id: str, text: str) -> None:  # noqa: D401
            logger.info("[MOCK TG] %s: %s", chat_id, text)

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
