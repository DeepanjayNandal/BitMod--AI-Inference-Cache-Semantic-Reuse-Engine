"""Messaging platform interface — for receiving and sending messages across chat platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class IncomingMessage:
    """A message received from any platform."""

    platform: str  # "telegram", "discord", "slack", etc.
    channel_id: str  # Platform-specific channel/chat ID
    user_id: str  # Platform-specific user ID
    username: str = ""  # Display name
    text: str = ""  # Message text
    reply_to: str | None = None  # Message being replied to
    attachments: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    """A message to send to a platform."""

    channel_id: str
    text: str
    reply_to: str | None = None
    metadata: dict = field(default_factory=dict)


class MessagingPlatform(ABC):
    """Abstract interface for messaging platform integrations."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Platform identifier (e.g., 'telegram', 'discord')."""

    @abstractmethod
    async def start(self, on_message: Callable[[IncomingMessage], Awaitable[str]]) -> None:
        """Start listening for messages. Calls on_message for each incoming message."""

    @abstractmethod
    async def send(self, message: OutgoingMessage) -> None:
        """Send a message to a channel/user."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the platform listener."""
