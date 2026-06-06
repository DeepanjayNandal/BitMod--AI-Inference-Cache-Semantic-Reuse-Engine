"""Matrix messaging adapter — uses Matrix Client-Server API."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx

from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform, OutgoingMessage

logger = logging.getLogger(__name__)


class MatrixAdapter(MessagingPlatform):
    """Matrix protocol adapter using Client-Server API."""

    def __init__(self, homeserver: str | None = None, token: str | None = None):
        self._homeserver = (homeserver or os.getenv("MATRIX_HOMESERVER", "https://matrix.org")).rstrip("/")  # type: ignore[union-attr]
        self._token = token or os.getenv("MATRIX_ACCESS_TOKEN", "")
        self._running = False

    @property
    def platform_name(self) -> str:
        return "matrix"

    async def start(self, on_message: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        logger.info("Matrix adapter started. Using long-polling sync.")
        self._running = True
        since = ""
        async with httpx.AsyncClient(timeout=60) as client:
            while self._running:
                try:
                    params: dict[str, str] = {"timeout": "30000"}
                    if since:
                        params["since"] = since
                    resp = await client.get(
                        f"{self._homeserver}/_matrix/client/v3/sync",
                        params=params,
                        headers={"Authorization": f"Bearer {self._token}"},
                    )
                    data = resp.json()
                    since = data.get("next_batch", since)

                    for room_id, room_data in data.get("rooms", {}).get("join", {}).items():
                        for event in room_data.get("timeline", {}).get("events", []):
                            if (
                                event.get("type") == "m.room.message"
                                and event.get("content", {}).get("msgtype") == "m.text"
                            ):
                                incoming = IncomingMessage(
                                    platform="matrix",
                                    channel_id=room_id,
                                    user_id=event["sender"],
                                    username=event["sender"].split(":")[0].lstrip("@"),
                                    text=event["content"]["body"],
                                )
                                response_text = await on_message(incoming)
                                await self.send(OutgoingMessage(channel_id=room_id, text=response_text))
                except Exception as e:
                    logger.error("Matrix sync error: %s", e)

    async def send(self, message: OutgoingMessage) -> None:
        txn_id = str(uuid.uuid4())
        encoded_room_id = quote(message.channel_id)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.put(
                    f"{self._homeserver}/_matrix/client/v3/rooms/{encoded_room_id}/send/m.room.message/{txn_id}",
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                    json={"msgtype": "m.text", "body": message.text},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error("Matrix send error: %s", e)

    async def stop(self) -> None:
        self._running = False
