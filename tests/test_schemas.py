"""Tests for Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from bitmod.schemas import ChatRequest, ChatResponse, SearchRequest


class TestChatRequest:
    def test_chat_request_validation(self):
        """Required fields must be present."""
        # Valid request
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"
        assert req.history == []
        assert req.filters == {}
        assert req.stream is False

    def test_chat_request_missing_message(self):
        """Missing required 'message' field raises ValidationError."""
        with pytest.raises(ValidationError):
            ChatRequest()

    def test_chat_request_with_history(self):
        """Request with conversation history."""
        req = ChatRequest(
            message="Follow up",
            history=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}],
        )
        assert len(req.history) == 2
        assert req.history[0].role == "user"


class TestChatResponse:
    def test_chat_response(self):
        """Response serialization."""
        resp = ChatResponse(
            answer="This is the answer.",
            cached=True,
            cache_key="abc123",
            sources=[{"section_id": "s1", "citation": "ref"}],
            model_used="test-model",
            generation_ms=150,
        )
        data = resp.model_dump()
        assert data["answer"] == "This is the answer."
        assert data["cached"] is True
        assert data["cache_key"] == "abc123"
        assert len(data["sources"]) == 1
        assert data["model_used"] == "test-model"
        assert data["generation_ms"] == 150

    def test_chat_response_defaults(self):
        """Response defaults."""
        resp = ChatResponse(answer="Answer")
        assert resp.cached is False
        assert resp.cache_key is None
        assert resp.sources == []


class TestSearchRequest:
    def test_search_request_limits(self):
        """Limit bounds validation: 1-100."""
        # Valid
        req = SearchRequest(query="test", limit=50)
        assert req.limit == 50

        # Default
        req = SearchRequest(query="test")
        assert req.limit == 10

        # Too low
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)

        # Too high
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=101)

    def test_search_request_requires_query(self):
        """Query field is required."""
        with pytest.raises(ValidationError):
            SearchRequest()
