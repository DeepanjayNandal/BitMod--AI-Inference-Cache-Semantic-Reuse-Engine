"""Tests for security utilities."""

import pytest

from bitmod.security import InMemoryRateLimiter, sanitize_html, sanitize_input


class TestSanitizeInput:
    def test_sanitize_input_preserves_html_for_llm(self):
        """HTML tags are preserved (not encoded) for LLM/cache input."""
        result = sanitize_input("<script>alert('xss')</script>")
        assert "<script>" in result  # preserved for LLM use
        assert "\x00" not in result  # null bytes still stripped

    def test_sanitize_input_null_bytes(self):
        """Null bytes are removed."""
        result = sanitize_input("hello\x00world")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_sanitize_input_length_limit(self):
        """Input is truncated to 10000 characters."""
        long_input = "a" * 20000
        result = sanitize_input(long_input)
        assert len(result) == 10000

    def test_sanitize_input_preserves_quotes(self):
        """Quotes are preserved (not encoded) for LLM/cache input."""
        result = sanitize_input('He said "hello" & \'goodbye\'')
        assert '"hello"' in result
        assert "'" in result


class TestSanitizeHtml:
    def test_sanitize_html(self):
        """All HTML tags are stripped."""
        result = sanitize_html("<p>Hello <b>world</b></p>")
        assert result == "Hello world"

    def test_sanitize_html_no_tags(self):
        """Plain text passes through unchanged."""
        result = sanitize_html("No tags here")
        assert result == "No tags here"


class TestRateLimiter:
    def test_rate_limiter_allows(self):
        """Requests within limit are allowed."""
        limiter = InMemoryRateLimiter()
        assert limiter.is_allowed("client1", max_requests=5, window_seconds=60) is True
        assert limiter.is_allowed("client1", max_requests=5, window_seconds=60) is True
        assert limiter.is_allowed("client1", max_requests=5, window_seconds=60) is True

    def test_rate_limiter_blocks(self):
        """Requests over limit are blocked."""
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.is_allowed("client2", max_requests=5, window_seconds=60)

        # 6th request should be blocked
        assert limiter.is_allowed("client2", max_requests=5, window_seconds=60) is False

    def test_rate_limiter_window_reset(self):
        """Window expiry allows new requests."""
        current_time = 1000.0

        def mock_clock() -> float:
            return current_time

        limiter = InMemoryRateLimiter(clock=mock_clock)
        # Fill up the limit with a very short window
        for _ in range(3):
            limiter.is_allowed("client3", max_requests=3, window_seconds=1)

        assert limiter.is_allowed("client3", max_requests=3, window_seconds=1) is False

        # Advance clock past the 1-second window
        current_time = 1001.1

        # Should be allowed again
        assert limiter.is_allowed("client3", max_requests=3, window_seconds=1) is True

    def test_rate_limiter_separate_clients(self):
        """Different clients have separate limits."""
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.is_allowed("clientA", max_requests=5, window_seconds=60)

        # clientA is at limit
        assert limiter.is_allowed("clientA", max_requests=5, window_seconds=60) is False
        # clientB is still fine
        assert limiter.is_allowed("clientB", max_requests=5, window_seconds=60) is True

    def test_rate_limiter_remaining(self):
        """Remaining count is accurate."""
        limiter = InMemoryRateLimiter()
        assert limiter.remaining("clientR", max_requests=5, window_seconds=60) == 5
        limiter.is_allowed("clientR", max_requests=5, window_seconds=60)
        assert limiter.remaining("clientR", max_requests=5, window_seconds=60) == 4
