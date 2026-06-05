"""WhatsApp messaging adapter — Meta Cloud API."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable

import httpx

from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform, OutgoingMessage

logger = logging.getLogger(__name__)


class WhatsAppAdapter(MessagingPlatform):
    """WhatsApp Business Cloud API adapter."""

    def __init__(self, token: str | None = None, phone_number_id: str | None = None):
        self._token = token or os.getenv("WHATSAPP_TOKEN", "")
        self._phone_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self._base_url = f"https://graph.facebook.com/v21.0/{self._phone_id}"
        self._running = False

    @property
    def platform_name(self) -> str:
        return "whatsapp"

    async def start(self, on_message: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        logger.info("WhatsApp adapter started. Configure webhook at /webhooks/whatsapp for incoming messages.")
        self._running = True

    async def send(self, message: OutgoingMessage) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": message.channel_id,
                        "type": "text",
                        "text": {"body": message.text},
                    },
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error("WhatsApp send error: %s", e)

    async def stop(self) -> None:
        self._running = False
