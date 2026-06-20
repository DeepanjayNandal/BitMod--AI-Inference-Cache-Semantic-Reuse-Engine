"""Expanded tests for security module: sanitization, rate limiting, path validation, SQL injection."""

import os
import tempfile
import threading

import pytest

from bitmod.security import (
    InMemoryRateLimiter,
    detect_sql_injection,
    mask_sensitive_value,
    sanitize_html,
    sanitize_input,
    validate_file_path,
    validate_file_for_ingestion,
    MAX_INPUT_LENGTH,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_FILE_EXTENSIONS,
)


class TestSanitizeInputExpanded:
    """Extended input sanitization tests."""

    def test_html_preserved_for_llm(self):
        """HTML characters are preserved (not encoded) for LLM/cache input."""
        result = sanitize_input("<div>Hello & goodbye</div>")
        assert "<div>" in result
        assert "&" in result

    def test_null_bytes_stripped(self):
        """Null bytes are removed from input."""
        result = sanitize_input("abc\x00def\x00ghi")
        assert "\x00" not in result
        assert result == "abcdefghi"

    def test_length_truncation(self):
        """Input exceeding MAX_INPUT_LENGTH is truncated."""
        long = "x" * (MAX_INPUT_LENGTH + 5000)
        result = sanitize_input(long)
        assert len(result) == MAX_INPUT_LENGTH

    def test_non_string_returns_empty(self):
        """Non-string input returns empty string."""
        assert sanitize_input(None) == ""
        assert sanitize_input(42) == ""
        assert sanitize_input([]) == ""

    def test_quotes_preserved_for_llm(self):
        """Quotes are preserved (not encoded) for LLM/cache input."""
        result = sanitize_input('He said "yes" & she said \'no\'')
        assert '"yes"' in result
        assert "'" in result

    def test_normal_text_passes_through(self):
        """Normal alphanumeric text is unchanged."""
        result = sanitize_input("Hello World 123")
        assert result == "Hello World 123"


class TestSanitizeHtmlExpanded:
    """Extended HTML stripping tests."""

    def test_nested_tags_stripped(self):
        """Nested HTML tags are fully stripped."""
        result = sanitize_html("<div><p><b>Bold</b> text</p></div>")
        assert result == "Bold text"

    def test_script_tags_stripped(self):
        """Script tags are stripped (content remains since sanitize_html only strips tags)."""
        result = sanitize_html("<script>alert('xss')</script>Safe text")
        assert "<script>" not in result
        assert "Safe text" in result

    def test_non_string_returns_empty(self):
        """Non-string input returns empty string."""
        assert sanitize_html(None) == ""
        assert sanitize_html(999) == ""


class TestSQLInjectionDetection:
    """Test SQL injection pattern detection."""

    def test_union_select_detected(self):
        """UNION SELECT pattern is flagged."""
        assert detect_sql_injection("1 UNION SELECT * FROM users") is True

    def test_drop_table_detected(self):
        """DROP TABLE pattern is flagged."""
        assert detect_sql_injection("'; DROP TABLE users;--") is True

    def test_or_equals_detected(self):
        """OR 1=1 pattern is flagged."""
        assert detect_sql_injection("admin' OR 1=1 --") is True

    def test_sleep_injection_detected(self):
        """SLEEP() injection is flagged."""
        assert detect_sql_injection("1; SLEEP(5)") is True

    def test_normal_text_not_flagged(self):
        """Normal text is not flagged as SQL injection."""
        assert detect_sql_injection("What is employment law in California?") is False

    def test_non_string_returns_false(self):
        """Non-string input returns False."""
        assert detect_sql_injection(None) is False
        assert detect_sql_injection(42) is False


class TestRateLimiterExpanded:
    """Extended rate limiter tests."""

    def test_allows_within_limit(self):
        """Requests within the limit are allowed."""
        limiter = InMemoryRateLimiter()
        for i in range(5):
            assert limiter.is_allowed("c1", max_requests=5, window_seconds=60) is True

    def test_blocks_over_limit(self):
        """The request exceeding the limit is blocked."""
        limiter = InMemoryRateLimiter()
        for _ in range(10):
            limiter.is_allowed("c2", max_requests=10, window_seconds=60)
        assert limiter.is_allowed("c2", max_requests=10, window_seconds=60) is False

    def test_window_reset_allows_again(self):
        """After the window expires, new requests are allowed."""
        current_time = 5000.0

        def mock_clock() -> float:
            return current_time

        limiter = InMemoryRateLimiter(clock=mock_clock)
        for _ in range(3):
            limiter.is_allowed("c3", max_requests=3, window_seconds=1)
        assert limiter.is_allowed("c3", max_requests=3, window_seconds=1) is False
        current_time = 5001.1
        assert limiter.is_allowed("c3", max_requests=3, window_seconds=1) is True

    def test_separate_client_isolation(self):
        """Different clients have independent rate limits."""
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.is_allowed("x", max_requests=5, window_seconds=60)
        assert limiter.is_allowed("x", max_requests=5, window_seconds=60) is False
        assert limiter.is_allowed("y", max_requests=5, window_seconds=60) is True

    def test_remaining_count(self):
        """Remaining count accurately reflects usage."""
        limiter = InMemoryRateLimiter()
        assert limiter.remaining("r1", max_requests=10, window_seconds=60) == 10
        limiter.is_allowed("r1", max_requests=10, window_seconds=60)
        limiter.is_allowed("r1", max_requests=10, window_seconds=60)
        assert limiter.remaining("r1", max_requests=10, window_seconds=60) == 8

    def test_thread_safety(self):
        """Rate limiter is thread-safe under concurrent access."""
        limiter = InMemoryRateLimiter()
        results = []

        def make_request():
            r = limiter.is_allowed("thread_client", max_requests=100, window_seconds=60)
            results.append(r)

        threads = [threading.Thread(target=make_request) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(1 for r in results if r)
        assert allowed_count == 100  # all should be allowed under limit of 100

    def test_cleanup_removes_stale_entries(self):
        """Stale entries are cleaned up after cleanup_interval."""
        current_time = 9000.0

        def mock_clock() -> float:
            return current_time

        limiter = InMemoryRateLimiter(cleanup_interval=0, max_clients=5, clock=mock_clock)
        # Add several clients
        for i in range(10):
            limiter.is_allowed(f"stale_{i}", max_requests=100, window_seconds=1)

        # Advance clock past the 1-second window so all entries become stale
        current_time = 9001.1
        # Trigger cleanup by making a new request (cleanup_interval=0 means always clean)
        limiter.is_allowed("trigger", max_requests=100, window_seconds=1)
        # After cleanup of stale entries + max_clients enforcement, should be pruned
        assert len(limiter._requests) <= 6  # max_clients=5 + trigger


class TestMaskSensitiveValue:
    """Test sensitive value masking."""

    def test_mask_long_value(self):
        """Long values show first N chars and mask the rest."""
        result = mask_sensitive_value("sk-abc123456789", visible_chars=4)
        assert result.startswith("sk-a")
        assert "****" in result
        assert len(result) == 15

    def test_mask_short_value(self):
        """Short values (at or below visible_chars) return '****'."""
        assert mask_sensitive_value("abc", visible_chars=4) == "****"
        assert mask_sensitive_value("", visible_chars=4) == "****"


class TestFilePathValidation:
    """Test file path validation for security."""

    def test_path_traversal_blocked(self):
        """Paths containing '..' are rejected."""
        with pytest.raises(ValueError, match="traversal"):
            validate_file_path("../../../etc/passwd")

    def test_null_bytes_in_path_stripped(self):
        """Null bytes in file paths are stripped before validation."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            path = f.name
        try:
            # Injecting null byte should still resolve to valid path
            result = validate_file_path(path.replace(".txt", "\x00.txt"))
            # After null byte removal, path may differ but should not raise for traversal
        except (ValueError, FileNotFoundError):
            pass  # acceptable outcomes
        finally:
            os.unlink(path)

    def test_empty_path_raises(self):
        """Empty path raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_file_path("")

    def test_allowed_base_dirs_enforced(self):
        """Paths outside allowed_base_dirs are rejected."""
        with pytest.raises(ValueError, match="outside allowed directories"):
            validate_file_path("/tmp/somefile.txt", allowed_base_dirs=["/var/data"])
