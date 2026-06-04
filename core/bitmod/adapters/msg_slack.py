"""Slack messaging adapter — uses Slack Web API."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable

import httpx

from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform, OutgoingMessage

logger = logging.getLogger(__name__)


class SlackAdapter(MessagingPlatform):
    """Slack adapter using Web API. For real-time events, use Slack Bolt."""

    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("SLACK_BOT_TOKEN", "")
        self._base_url = "https://slack.com/api"
        self._running = False

    @property
    def platform_name(self) -> str:
        return "slack"

    async def start(self, on_message: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        logger.info("Slack adapter started. Configure Slack Events API webhook for real-time messages.")
        self._running = True

    async def send(self, message: OutgoingMessage) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/chat.postMessage",
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                    json={"channel": message.channel_id, "text": message.text},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error("Slack send error: %s", e)

    async def stop(self) -> None:
        self._running = False
