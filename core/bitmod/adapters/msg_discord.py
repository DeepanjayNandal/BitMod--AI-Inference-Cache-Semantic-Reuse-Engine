"""Discord messaging adapter — REST API + Gateway WebSocket."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable

import httpx

from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform, OutgoingMessage

logger = logging.getLogger(__name__)


class DiscordAdapter(MessagingPlatform):
    """Discord bot adapter using REST API."""

    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("DISCORD_BOT_TOKEN", "")
        self._base_url = "https://discord.com/api/v10"
        self._headers = {"Authorization": f"Bot {self._token}", "Content-Type": "application/json"}
        self._running = False

    @property
    def platform_name(self) -> str:
        return "discord"

    async def start(self, on_message: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        """Start the Discord adapter in REST-only mode.

        This adapter is REST-only and can only send messages via the Discord
        REST API. Incoming message handling requires a Discord Gateway
        (WebSocket) connection, which is not implemented here. For full
        bidirectional support, use the discord.py library.
        """
        logger.warning(
            "Discord adapter is REST-only. Incoming message handling requires Discord Gateway (not implemented)."
        )
        self._running = True

    async def send(self, message: OutgoingMessage) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/channels/{message.channel_id}/messages",
                    headers=self._headers,
                    json={"content": message.text},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error("Discord send error: %s", e)

    async def stop(self) -> None:
        self._running = False
