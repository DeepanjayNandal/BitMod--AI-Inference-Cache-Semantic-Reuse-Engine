"""Tests for the cache qualification layer."""

from __future__ import annotations

from bitmod.cache_qualify import (
    QualificationResult,
    is_context_dependent,
    qualify_cache_hit,
)


# ---------------------------------------------------------------------------
# Context-Dependent Detection
# ---------------------------------------------------------------------------


class TestContextDependent:
    def test_anaphoric_references(self):
        assert is_context_dependent("tell me more")
        assert is_context_dependent("explain that")
        assert is_context_dependent("go deeper")
        assert is_context_dependent("what do you mean")
        assert is_context_dependent("elaborate on that")

    def test_continuation_phrases(self):
        assert is_context_dependent("what's next")
        assert is_context_dependent("what else")
        assert is_context_dependent("continue")
        assert is_context_dependent("go on")
        assert is_context_dependent("anything else")

    def test_pronoun_queries(self):
        assert is_context_dependent("what is it")
        assert is_context_dependent("how does it work")
        assert is_context_dependent("why does it matter")
        assert is_context_dependent("where is it")

    def test_conversational_commands(self):
        assert is_context_dependent("yes")
        assert is_context_dependent("no")
        assert is_context_dependent("sure")
        assert is_context_dependent("exactly")
        assert is_context_dependent("summarize that")

    def test_short_query_with_history(self):
        history = [{"role": "user", "content": "What is HIPAA?"}]
        assert is_context_dependent("and GDPR?", history=history)
        assert is_context_dependent("more", history=history)

    def test_normal_queries_not_flagged(self):
        assert not is_context_dependent("What is HIPAA?")
        assert not is_context_dependent("Explain quantum computing")
        assert not is_context_dependent("How does RSA encryption work?")
        assert not is_context_dependent("What are the SOLID principles?")
        assert not is_context_dependent("Compare Python and JavaScript")

    def test_short_query_without_history(self):
        assert not is_context_dependent("What is HIPAA?")

    def test_empty_query(self):
        assert not is_context_dependent("")

    def test_longer_query_with_context_phrase(self):
        assert is_context_dependent("can you tell me more about that topic?")


# ---------------------------------------------------------------------------
# Full Qualification Gate
# ---------------------------------------------------------------------------


class TestQualifyCacheHit:
    def test_normal_hit_serves(self):
        result = qualify_cache_hit(
            query="What is HIPAA?",
            cached_answer="HIPAA stands for the Health Insurance Portability and Accountability Act.",
        )
        assert result.serve is True

    def test_context_dependent_skips(self):
        result = qualify_cache_hit(
            query="tell me more",
            cached_answer="Here is more detail about the topic.",
            history=[{"role": "user", "content": "What is HIPAA?"}],
        )
        assert result.serve is False
        assert result.check == "context_dependent"

    def test_short_query_with_history_skips(self):
        result = qualify_cache_hit(
            query="hello",
            cached_answer="Hello! How can I help?",
            history=[{"role": "user", "content": "Tell me about encryption"}],
        )
        assert result.serve is False
        assert result.check == "context_dependent"

    def test_normal_query_with_history_serves(self):
        result = qualify_cache_hit(
            query="What is the capital of France?",
            cached_answer="The capital of France is Paris.",
            history=[{"role": "user", "content": "Tell me about encryption"}],
        )
        assert result.serve is True

    def test_no_history_serves(self):
        result = qualify_cache_hit(
            query="hello",
            cached_answer="Hello! How can I help?",
        )
        assert result.serve is True

    def test_extra_kwargs_ignored(self):
        result = qualify_cache_hit(
            query="What is HIPAA?",
            cached_answer="HIPAA is a US healthcare law.",
            cached_model="llama3.2",
            requested_model="gpt-4o",
            max_tokens=4000,
        )
        assert result.serve is True

    def test_result_to_dict(self):
        result = QualificationResult(serve=False, reason="test reason", check="test_check")
        d = result.to_dict()
        assert d["serve"] is False
        assert d["reason"] == "test reason"
        assert d["check"] == "test_check"
