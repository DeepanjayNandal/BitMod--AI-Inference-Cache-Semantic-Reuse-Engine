"""Messaging Bridge — connects any messaging platform to BitMod's AI pipeline.

Usage:
    from bitmod.messaging_bridge import MessagingBridge
    from bitmod.adapters.msg_telegram import TelegramAdapter

    bridge = MessagingBridge(backend=my_backend, llm=my_llm)
    bridge.register(TelegramAdapter(token="..."))
    await bridge.start_all()
"""

import asyncio
import logging

from bitmod.cache_engine import compute_answer_key, normalize_query, store_answer, try_cache
from bitmod.interfaces.database import DatabaseBackend
from bitmod.interfaces.llm import LLMMessage, LLMProvider
from bitmod.interfaces.messaging import IncomingMessage, MessagingPlatform
from bitmod.security import sanitize_input

logger = logging.getLogger(__name__)


class MessagingBridge:
    """Bridges messaging platforms to BitMod's AI pipeline with caching."""

    def __init__(self, backend: DatabaseBackend, llm: LLMProvider):
        self._backend = backend
        self._llm = llm
        self._platforms: list[MessagingPlatform] = []

    def register(self, platform: MessagingPlatform) -> None:
        """Register a messaging platform."""
        self._platforms.append(platform)
        logger.info("Registered messaging platform: %s", platform.platform_name)

    async def handle_message(self, msg: IncomingMessage) -> str:
        """Process an incoming message through BitMod's pipeline.

        1. Check cache
        2. If miss, generate via LLM
        3. Cache the answer
        4. Return response text
        """
        query = sanitize_input(msg.text).strip()
        if not query:
            return "Please send a message."

        filters = {"platform": msg.platform, "channel": msg.channel_id}

        # Try cache first
        with self._backend.session() as session:
            cached = try_cache(self._backend, session, query, filters)
            if cached:
                logger.info("[%s] Cache HIT for: %s", msg.platform, query[:50])
                return cached.answer_text

        # Generate fresh answer
        messages = [
            LLMMessage(role="system", content="You are BitMod, an AI assistant. Be concise and helpful."),
            LLMMessage(role="user", content=query),
        ]

        try:
            response = await self._llm.generate(messages)
            answer = response.content

            # Cache it
            answer_key = compute_answer_key(query, filters)
            with self._backend.session() as session:
                store_answer(
                    self._backend,
                    session,
                    answer_key=answer_key,
                    question_raw=query,
                    question_normalized=normalize_query(query),
                    filters=filters,
                    answer_text=answer,
                    source_sections=[],
                    model_used=response.model,
                    generation_ms=0,
                )

            return answer
        except Exception as e:
            logger.error("[%s] LLM generation failed: %s", msg.platform, e)
            return "Sorry, I encountered an error. Please try again."

    async def start_all(self) -> None:
        """Start all registered platforms."""
        tasks = [p.start(self.handle_message) for p in self._platforms]
        await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        """Stop all registered platforms."""
        for p in self._platforms:
            await p.stop()
