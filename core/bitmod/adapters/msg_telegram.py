"""Telegram messaging adapter — uses Telegram Bot API with long polling."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable

import httpx

from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform, OutgoingMessage

logger = logging.getLogger(__name__)


class TelegramAdapter(MessagingPlatform):
    """Telegram Bot API adapter using long polling."""

    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._base_url = f"https://api.telegram.org/bot{self._token}"
        self._running = False
        self._offset = 0

    @property
    def platform_name(self) -> str:
        return "telegram"

    async def start(self, on_message: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        self._running = True
        async with httpx.AsyncClient(timeout=60) as client:
            while self._running:
                try:
                    resp = await client.get(
                        f"{self._base_url}/getUpdates",
                        params={"offset": self._offset, "timeout": 30},
                    )
                    data = resp.json()
                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        if not msg.get("text"):
                            continue

                        incoming = IncomingMessage(
                            platform="telegram",
                            channel_id=str(msg["chat"]["id"]),
                            user_id=str(msg["from"]["id"]),
                            username=msg["from"].get("username", msg["from"].get("first_name", "")),
                            text=msg["text"],
                            reply_to=str(msg["reply_to_message"]["message_id"])
                            if msg.get("reply_to_message")
                            else None,
                        )

                        response_text = await on_message(incoming)
                        await self.send(
                            OutgoingMessage(
                                channel_id=incoming.channel_id,
                                text=response_text,
                            )
                        )
                except Exception as e:
                    logger.error("Telegram polling error: %s", e)

    async def send(self, message: OutgoingMessage) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/sendMessage",
                    json={"chat_id": message.channel_id, "text": message.text, "parse_mode": "Markdown"},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error("Telegram send error: %s", e)

    async def stop(self) -> None:
        self._running = False
