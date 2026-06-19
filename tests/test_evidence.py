"""Tests for pipeline evidence accumulation and atomic fact decomposition."""

from __future__ import annotations

import math

import pytest

from bitmod.cache_engine import (
    CacheEvidence,
    PipelineEvidence,
    SemanticMatch,
    _similarity_to_confidence,
    decompose_answer,
)
from bitmod.interfaces.database import AnswerCacheRecord


class TestCacheEvidence:
    """Verify CacheEvidence dataclass creation and field defaults."""

    def test_basic_creation(self):
        ev = CacheEvidence(layer="exact", confidence=0.95, answer_text="Answer here.")
        assert ev.layer == "exact"
        assert ev.confidence == 0.95
        assert ev.answer_text == "Answer here."

    def test_defaults(self):
        ev = CacheEvidence(layer="semantic", confidence=0.8, answer_text="text")
        assert ev.record_id is None
        assert ev.similarity == 0.0
        assert ev.is_partial is False
        assert ev.sub_query == ""
        assert ev.metadata == {}

    def test_all_fields(self):
        ev = CacheEvidence(
            layer="composable",
            confidence=0.6,
            answer_text="partial",
            record_id="rec-1",
            similarity=0.88,
            is_partial=True,
            sub_query="sub q",
            metadata={"source": "test"},
        )
        assert ev.record_id == "rec-1"
        assert ev.similarity == 0.88
        assert ev.is_partial is True
        assert ev.sub_query == "sub q"
        assert ev.metadata == {"source": "test"}


class TestPipelineEvidence:
    """Verify evidence accumulation with Bayesian confidence stacking."""

    def test_empty_pipeline(self):
        pe = PipelineEvidence()
        assert pe.total_confidence == 0.0
        assert pe.decision == "GENERATE"
        assert pe.evidences == []

    def test_single_evidence(self):
        """Single evidence at 0.85 -> total confidence = 0.85."""
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="exact", confidence=0.85, answer_text="a"))
        assert pe.total_confidence == pytest.approx(0.85)

    def test_bayesian_stacking(self):
        """0.85 + 0.50 -> 1 - (0.15 * 0.50) = 0.925."""
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="exact", confidence=0.85, answer_text="a"))
        pe.add(CacheEvidence(layer="semantic", confidence=0.50, answer_text="b"))
        expected = 1.0 - (0.15 * 0.50)
        assert pe.total_confidence == pytest.approx(expected)

    def test_triple_stacking(self):
        """Three evidence pieces stack correctly."""
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="exact", confidence=0.80, answer_text="a"))
        pe.add(CacheEvidence(layer="semantic", confidence=0.60, answer_text="b"))
        pe.add(CacheEvidence(layer="fuzzy", confidence=0.40, answer_text="c"))
        expected = 1.0 - (0.20 * 0.40 * 0.60)
        assert pe.total_confidence == pytest.approx(expected)

    def test_zero_confidence_no_effect(self):
        """Evidence with 0.0 confidence does not change total."""
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="exact", confidence=0.70, answer_text="a"))
        pe.add(CacheEvidence(layer="semantic", confidence=0.0, answer_text="b"))
        assert pe.total_confidence == pytest.approx(0.70)

    def test_perfect_confidence(self):
        """Evidence at 1.0 drives total to 1.0 regardless of others."""
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="exact", confidence=1.0, answer_text="a"))
        pe.add(CacheEvidence(layer="semantic", confidence=0.50, answer_text="b"))
        assert pe.total_confidence == pytest.approx(1.0)


class TestBestSingleAnswer:
    """Verify best_single_answer returns highest-confidence non-partial evidence."""

    def test_returns_highest_non_partial(self):
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="fuzzy", confidence=0.60, answer_text="low"))
        pe.add(CacheEvidence(layer="exact", confidence=0.95, answer_text="high"))
        pe.add(CacheEvidence(layer="composable", confidence=0.99, answer_text="partial", is_partial=True))
        best = pe.best_single_answer()
        assert best is not None
        assert best.answer_text == "high"
        assert best.confidence == 0.95

    def test_returns_none_when_all_partial(self):
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="composable", confidence=0.80, answer_text="p1", is_partial=True))
        pe.add(CacheEvidence(layer="composable", confidence=0.90, answer_text="p2", is_partial=True))
        assert pe.best_single_answer() is None

    def test_returns_none_when_empty(self):
        pe = PipelineEvidence()
        assert pe.best_single_answer() is None


class TestContextForLlm:
    """Verify context_for_llm assembles all evidence sorted by confidence."""

    def test_assembles_all_evidence(self):
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="fuzzy", confidence=0.40, answer_text="Fuzzy result."))
        pe.add(CacheEvidence(layer="exact", confidence=0.95, answer_text="Exact result."))
        ctx = pe.context_for_llm()
        # Higher confidence first
        assert ctx.index("exact") < ctx.index("fuzzy")
        assert "[exact:0.95]" in ctx
        assert "[fuzzy:0.40]" in ctx
        assert "---" in ctx

    def test_includes_sub_query_label(self):
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="composable", confidence=0.70, answer_text="Answer.",
                             sub_query="privacy in CA"))
        ctx = pe.context_for_llm()
        assert "(re: privacy in CA)" in ctx

    def test_skips_empty_answer_text(self):
        pe = PipelineEvidence()
        pe.add(CacheEvidence(layer="exact", confidence=0.90, answer_text=""))
        pe.add(CacheEvidence(layer="fuzzy", confidence=0.50, answer_text="Has content."))
        ctx = pe.context_for_llm()
        assert "exact" not in ctx
        assert "Has content." in ctx


class TestSimilarityToConfidence:
    """Verify the non-linear similarity-to-confidence mapping curves."""

    def test_semantic_high(self):
        """>=0.98 maps to 0.99."""
        assert _similarity_to_confidence(0.98, "semantic") == pytest.approx(0.99)
        assert _similarity_to_confidence(1.00, "semantic") == pytest.approx(0.99)

    def test_semantic_good(self):
        """0.92 maps to 0.85."""
        assert _similarity_to_confidence(0.92, "semantic") == pytest.approx(0.85)

    def test_semantic_moderate(self):
        """0.85 maps to 0.55."""
        assert _similarity_to_confidence(0.85, "semantic") == pytest.approx(0.55)

    def test_semantic_low(self):
        """0.75 maps to 0.25."""
        assert _similarity_to_confidence(0.75, "semantic") == pytest.approx(0.25)

    def test_semantic_below_threshold(self):
        """Below 0.75 returns 0.0."""
        assert _similarity_to_confidence(0.70, "semantic") == 0.0
        assert _similarity_to_confidence(0.50, "semantic") == 0.0

    def test_fuzzy_high(self):
        """>=0.95 maps to 0.80."""
        assert _similarity_to_confidence(0.95, "fuzzy") == pytest.approx(0.80)
        assert _similarity_to_confidence(0.99, "fuzzy") == pytest.approx(0.80)

    def test_fuzzy_moderate(self):
        """0.90 maps to 0.50."""
        assert _similarity_to_confidence(0.90, "fuzzy") == pytest.approx(0.50)

    def test_fuzzy_low(self):
        """Below 0.85 returns 0.15."""
        assert _similarity_to_confidence(0.80, "fuzzy") == pytest.approx(0.15)

    def test_unknown_layer_passthrough(self):
        """Unknown layer returns raw similarity."""
        assert _similarity_to_confidence(0.77, "unknown") == pytest.approx(0.77)


class TestSemanticMatch:
    """Verify SemanticMatch dataclass."""

    def test_creation(self):
        record = AnswerCacheRecord(answer_key="k", answer_text="Answer.")
        sm = SemanticMatch(record=record, similarity=0.93)
        assert sm.record.answer_text == "Answer."
        assert sm.similarity == 0.93


class TestDecomposeAnswer:
    """Verify atomic fact decomposition: splitting, filtering, categorization."""

    def test_splits_sentences(self):
        text = "Python is a programming language. It was created by Guido van Rossum."
        facts = decompose_answer(text)
        assert len(facts) == 2

    def test_filters_short_sentences(self):
        text = "Python is great. It was created by Guido van Rossum in the early 1990s."
        facts = decompose_answer(text)
        # "Python is great." is < 20 chars, should be filtered
        assert len(facts) == 1
        assert "Guido" in facts[0]["fact_text"]

    def test_filters_filler_sentences(self):
        text = (
            "However this leads to many issues in practice. "
            "The regulation requires companies to notify within 72 hours."
        )
        facts = decompose_answer(text)
        fillers = [f for f in facts if f["fact_text"].startswith("However")]
        assert len(fillers) == 0

    def test_filters_questions(self):
        text = "What do you think about this? The rule requires a 30-day notice period."
        facts = decompose_answer(text)
        questions = [f for f in facts if f["fact_text"].endswith("?")]
        assert len(questions) == 0

    def test_categorizes_definition(self):
        text = "Privacy is defined as the right to be left alone without intrusion."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "definition"

    def test_categorizes_rule(self):
        text = "Companies must report breaches within 72 hours of discovery."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "rule"

    def test_categorizes_comparison(self):
        text = "California's law differs significantly from the federal standard."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "comparison"

    def test_categorizes_procedure(self):
        text = "First you submit the application, then wait for the review process."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "procedure"

    def test_categorizes_statistic(self):
        text = "The company generated $5 billion in revenue last fiscal year."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "statistic"

    def test_categorizes_general(self):
        text = "The California Consumer Privacy Act was signed into law in 2018."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "general"

    def test_extracts_entity(self):
        text = "The European Union enacted the General Data Protection Regulation."
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["entity"] != ""

    def test_empty_input(self):
        assert decompose_answer("") == []

    def test_multiple_filler_patterns(self):
        text = (
            "Additionally there are other considerations here. "
            "I hope this helps you understand the regulations better. "
            "Let me know if you have any further questions about this. "
            "The penalty for non-compliance is $10 million per violation."
        )
        facts = decompose_answer(text)
        assert len(facts) == 1
        assert facts[0]["category"] == "statistic"
