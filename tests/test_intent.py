"""Tests for the Bitmod Intent Detection Engine.

Covers:
- All intent action types
- Confidence scoring
- Entity extraction
- Format/depth detection
- YAML intent registry loading
- Role routing
"""

import pytest
from pathlib import Path

from bitmod.intent import (
    IntentAction,
    IntentFormat,
    IntentDepth,
    IntentMode,
    DetectedIntent,
    IntentRegistry,
    detect_intent,
    detect_format,
    detect_depth,
    extract_entities,
)
from bitmod.roles import Role, RoleConfig, RoleRegistry


# =========================================================================
# Intent Action Detection
# =========================================================================

class TestPassiveRetrieval:
    """Test passive retrieval intent detection."""

    def test_cite_start(self):
        r = detect_intent("Cite the relevant statute")
        assert r.action == IntentAction.CITE
        assert r.confidence == 1.0

    def test_citation_for(self):
        r = detect_intent("What is the citation for this regulation?")
        assert r.action == IntentAction.CITE
        assert r.confidence == 0.9

    def test_list_start(self):
        r = detect_intent("List all requirements")
        assert r.action == IntentAction.LIST
        assert r.confidence == 1.0

    def test_give_me_a_list(self):
        r = detect_intent("Give me a list of countries")
        assert r.action == IntentAction.LIST
        assert r.confidence == 0.9

    def test_quote_start(self):
        r = detect_intent("Quote the first paragraph")
        assert r.action == IntentAction.QUOTE
        assert r.confidence == 1.0

    def test_exact_text(self):
        r = detect_intent("What is the exact text of section 5?")
        assert r.action == IntentAction.QUOTE

    def test_find_start(self):
        r = detect_intent("Find all references to climate change")
        assert r.action == IntentAction.FIND
        assert r.confidence == 1.0

    def test_show_me(self):
        r = detect_intent("Show me the latest data")
        assert r.action == IntentAction.SHOW
        assert r.confidence == 1.0

    def test_lookup(self):
        r = detect_intent("Look up the definition of arbitrage")
        assert r.action == IntentAction.LOOKUP


class TestSynthesis:
    """Test synthesis intent detection."""

    def test_summarize_start(self):
        r = detect_intent("Summarize this document")
        assert r.action == IntentAction.SUMMARIZE
        assert r.confidence == 1.0

    def test_tldr(self):
        r = detect_intent("tl;dr of the report")
        assert r.action == IntentAction.SUMMARIZE

    def test_explain_start(self):
        r = detect_intent("Explain how photosynthesis works")
        assert r.action == IntentAction.EXPLAIN
        assert r.confidence == 1.0

    def test_what_does_mean(self):
        r = detect_intent("What does habeas corpus mean?")
        assert r.action == IntentAction.EXPLAIN

    def test_compare_start(self):
        r = detect_intent("Compare Python and JavaScript")
        assert r.action == IntentAction.COMPARE
        assert r.confidence == 1.0

    def test_differences_between(self):
        r = detect_intent("What are the differences between TCP and UDP?")
        assert r.action == IntentAction.COMPARE

    def test_vs(self):
        r = detect_intent("React vs Angular for enterprise apps")
        assert r.action == IntentAction.COMPARE

    def test_contrast(self):
        r = detect_intent("Contrast the two approaches")
        assert r.action == IntentAction.CONTRAST
        assert r.confidence == 1.0


class TestReasoning:
    """Test reasoning intent detection."""

    def test_analyze_start(self):
        r = detect_intent("Analyze the market trends")
        assert r.action == IntentAction.ANALYZE
        assert r.confidence == 1.0

    def test_analyse_british(self):
        r = detect_intent("Analyse the data set")
        assert r.action == IntentAction.ANALYZE

    def test_evaluate(self):
        r = detect_intent("Evaluate the performance of this approach")
        assert r.action == IntentAction.EVALUATE
        assert r.confidence == 1.0

    def test_hypothesize(self):
        r = detect_intent("Hypothesize about the cause of the failure")
        assert r.action == IntentAction.HYPOTHESIZE

    def test_what_if(self):
        r = detect_intent("What if we doubled the budget?")
        assert r.action == IntentAction.HYPOTHESIZE

    def test_think_through(self):
        r = detect_intent("Think through the implications of this policy")
        assert r.action == IntentAction.THINK

    def test_pros_and_cons(self):
        r = detect_intent("What are the pros and cons of remote work?")
        assert r.action == IntentAction.DEBATE

    def test_predict(self):
        r = detect_intent("Predict the outcome of the election")
        assert r.action == IntentAction.PREDICT


class TestAgentic:
    """Test agentic intent detection."""

    def test_execute(self):
        r = detect_intent("Execute the migration script")
        assert r.action == IntentAction.EXECUTE
        assert r.confidence == 1.0
        assert r.mode == IntentMode.ACTIONABLE

    def test_run(self):
        r = detect_intent("Run the test suite")
        assert r.action == IntentAction.EXECUTE

    def test_build(self):
        r = detect_intent("Build a REST API for user management")
        assert r.action == IntentAction.BUILD
        assert r.mode == IntentMode.ACTIONABLE

    def test_deploy(self):
        r = detect_intent("Deploy the service to production")
        assert r.action == IntentAction.DEPLOY

    def test_transform(self):
        r = detect_intent("Transform the CSV data into a graph")
        assert r.action == IntentAction.TRANSFORM


class TestDeterministic:
    """Test deterministic (zero-LLM) intent detection."""

    def test_extract(self):
        r = detect_intent("Extract all email addresses from the document")
        assert r.action == IntentAction.EXTRACT
        assert r.skip_llm is True
        assert r.mode == IntentMode.DETERMINISTIC

    def test_convert(self):
        r = detect_intent("Convert 100 USD to EUR")
        assert r.action == IntentAction.CONVERT
        assert r.skip_llm is True

    def test_count(self):
        r = detect_intent("Count the number of sections")
        assert r.action == IntentAction.COUNT
        assert r.skip_llm is True

    def test_how_many(self):
        r = detect_intent("How many patents were filed in 2024?")
        assert r.action == IntentAction.COUNT
        assert r.skip_llm is True

    def test_calculate(self):
        r = detect_intent("Calculate the total revenue")
        assert r.action == IntentAction.CALCULATE
        assert r.skip_llm is True

    def test_validate(self):
        r = detect_intent("Validate the JSON schema")
        assert r.action == IntentAction.VALIDATE
        assert r.skip_llm is True


class TestCreative:
    """Test creative intent detection."""

    def test_brainstorm(self):
        r = detect_intent("Brainstorm ideas for the marketing campaign")
        assert r.action == IntentAction.BRAINSTORM
        assert r.mode == IntentMode.CREATIVE
        assert r.cacheable is False

    def test_create(self):
        r = detect_intent("Create a dashboard layout")
        assert r.action == IntentAction.CREATE
        assert r.cacheable is False

    def test_write(self):
        r = detect_intent("Write a press release about the new product")
        assert r.action == IntentAction.WRITE
        assert r.mode == IntentMode.CREATIVE

    def test_draft(self):
        r = detect_intent("Draft a proposal for the client")
        assert r.action == IntentAction.DRAFT

    def test_generate(self):
        r = detect_intent("Generate a list of test cases")
        assert r.action == IntentAction.GENERATE

    def test_compose(self):
        r = detect_intent("Compose an email to the team")
        assert r.action == IntentAction.COMPOSE
        assert r.cacheable is False


class TestEdgeCases:
    """Test edge cases and fallbacks."""

    def test_empty_query(self):
        r = detect_intent("")
        assert r.action == IntentAction.UNKNOWN
        assert r.confidence == 0.0

    def test_whitespace_query(self):
        r = detect_intent("   ")
        assert r.action == IntentAction.UNKNOWN

    def test_unknown_intent(self):
        r = detect_intent("Hello there")
        assert r.action == IntentAction.UNKNOWN
        assert r.confidence == 0.0

    def test_tier_is_always_one(self):
        r = detect_intent("Summarize the report")
        assert r.tier == 1

    def test_raw_query_preserved(self):
        r = detect_intent("Compare apples and oranges")
        assert r.raw_query == "Compare apples and oranges"


# =========================================================================
# Confidence Scoring
# =========================================================================

class TestConfidence:
    """Test confidence scoring levels."""

    def test_exact_match_high_confidence(self):
        r = detect_intent("Summarize this article")
        assert r.confidence == 1.0

    def test_mid_match_confidence(self):
        r = detect_intent("Can you summarize the key points?")
        assert 0.8 <= r.confidence <= 1.0

    def test_weak_match_confidence(self):
        r = detect_intent("What is the difference between X and Y vs Z")
        assert r.confidence >= 0.7

    def test_no_match_zero_confidence(self):
        r = detect_intent("I like pizza")
        assert r.confidence == 0.0


# =========================================================================
# Format Detection
# =========================================================================

class TestFormatDetection:
    """Test output format detection."""

    def test_table_format(self):
        fmt = detect_format("Show the data as a table", IntentAction.SHOW)
        assert fmt == IntentFormat.TABLE

    def test_bullet_format(self):
        fmt = detect_format("Give me the key points in bullet points", IntentAction.SUMMARIZE)
        assert fmt == IntentFormat.BULLETS

    def test_json_format(self):
        fmt = detect_format("Return the results as json", IntentAction.EXTRACT)
        assert fmt == IntentFormat.JSON

    def test_csv_format(self):
        fmt = detect_format("Export as CSV", IntentAction.EXTRACT)
        assert fmt == IntentFormat.CSV

    def test_code_format(self):
        fmt = detect_format("Give me the solution as code", IntentAction.BUILD)
        assert fmt == IntentFormat.CODE

    def test_default_for_list(self):
        fmt = detect_format("List the items", IntentAction.LIST)
        assert fmt == IntentFormat.BULLETS

    def test_default_for_compare(self):
        fmt = detect_format("Compare X and Y", IntentAction.COMPARE)
        assert fmt == IntentFormat.TABLE

    def test_auto_for_unknown(self):
        fmt = detect_format("Tell me about cats", IntentAction.UNKNOWN)
        assert fmt == IntentFormat.AUTO

    def test_format_in_full_detection(self):
        r = detect_intent("List all requirements as a table")
        assert r.format == IntentFormat.TABLE  # explicit overrides implicit


# =========================================================================
# Depth Detection
# =========================================================================

class TestDepthDetection:
    """Test depth detection."""

    def test_brief(self):
        d = detect_depth("Briefly explain the concept")
        assert d == IntentDepth.BRIEF

    def test_quickly(self):
        d = detect_depth("Quickly summarize the report")
        assert d == IntentDepth.BRIEF

    def test_tldr_brief(self):
        d = detect_depth("Give me the tldr")
        assert d == IntentDepth.BRIEF

    def test_detailed(self):
        d = detect_depth("Give me a detailed analysis")
        assert d == IntentDepth.DETAILED

    def test_in_depth(self):
        d = detect_depth("Provide an in-depth review")
        assert d == IntentDepth.DETAILED

    def test_exhaustive(self):
        d = detect_depth("Tell me everything about this topic")
        assert d == IntentDepth.EXHAUSTIVE

    def test_standard_default(self):
        d = detect_depth("Tell me about cats")
        assert d == IntentDepth.STANDARD

    def test_depth_in_full_detection(self):
        r = detect_intent("Briefly summarize the report")
        assert r.depth == IntentDepth.BRIEF


# =========================================================================
# Entity Extraction
# =========================================================================

class TestEntityExtraction:
    """Test entity extraction from queries."""

    def test_quoted_string(self):
        entities = extract_entities('Find the section titled "Due Process"')
        assert "Due Process" in entities

    def test_single_quoted(self):
        entities = extract_entities("Explain the term 'force majeure'")
        assert "force majeure" in entities

    def test_proper_nouns(self):
        entities = extract_entities("Compare New York and Los Angeles")
        assert any("New York" in e for e in entities)

    def test_numbers_with_units(self):
        entities = extract_entities("Convert 100 USD to EUR")
        assert any("100" in e for e in entities)

    def test_url(self):
        entities = extract_entities("Summarize https://example.com/article")
        assert "https://example.com/article" in entities

    def test_email(self):
        entities = extract_entities("Find emails from user@example.com")
        assert "user@example.com" in entities

    def test_codes(self):
        entities = extract_entities("What does HIPAA say about data privacy?")
        assert "HIPAA" in entities

    def test_no_common_words(self):
        entities = extract_entities("List all the items")
        # Common uppercase words like LIST, THE should be excluded
        assert "LIST" not in entities
        assert "THE" not in entities

    def test_empty_query(self):
        entities = extract_entities("")
        assert entities == []

    def test_entities_in_full_detection(self):
        r = detect_intent('Find the section titled "Due Process" in HIPAA')
        assert "Due Process" in r.entities
        assert "HIPAA" in r.entities


# =========================================================================
# YAML Intent Registry
# =========================================================================

class TestIntentRegistry:
    """Test YAML intent loading and registry."""

    def test_load_default_intents(self):
        registry = IntentRegistry()
        registry.load()
        assert registry.loaded is True
        assert len(registry.all_names()) >= 15

    def test_get_summarize(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get("summarize")
        assert config is not None
        assert config.name == "summarize"
        assert config.role == "synthesizer"
        assert config.cacheable is True

    def test_get_extract(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get("extract")
        assert config is not None
        assert config.skip_llm is True

    def test_get_execute(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get("execute")
        assert config is not None
        assert config.cacheable is False

    def test_get_brainstorm(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get("brainstorm")
        assert config is not None
        assert config.cacheable is False
        assert config.cache_ttl == 0

    def test_get_for_action(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get_for_action(IntentAction.COMPARE)
        assert config is not None
        assert config.name == "compare"

    def test_get_nonexistent(self):
        registry = IntentRegistry()
        registry.load()
        assert registry.get("nonexistent") is None

    def test_reload(self):
        registry = IntentRegistry()
        registry.load()
        count1 = len(registry.all_names())
        registry.reload()
        count2 = len(registry.all_names())
        assert count1 == count2

    def test_auto_load_on_get(self):
        registry = IntentRegistry()
        # Should auto-load when accessing
        config = registry.get("summarize")
        assert config is not None
        assert registry.loaded is True

    def test_empty_directory(self, tmp_path):
        registry = IntentRegistry(intents_dir=tmp_path)
        registry.load()
        assert registry.loaded is True
        assert len(registry.all_names()) == 0

    def test_token_budget_types(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get("compare")
        assert isinstance(config.token_budget, int)
        assert config.token_budget > 0

    def test_cache_ttl_types(self):
        registry = IntentRegistry()
        registry.load()
        config = registry.get("cite")
        assert isinstance(config.cache_ttl, int)
        assert config.cache_ttl == 86400


# =========================================================================
# Role Routing
# =========================================================================

class TestRoleRouting:
    """Test role routing from intents."""

    def test_cite_to_narrator(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Cite the relevant statute")
        role, config = registry.resolve(intent)
        assert role == Role.NARRATOR

    def test_compare_to_synthesizer(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Compare Python and JavaScript")
        role, config = registry.resolve(intent)
        assert role == Role.SYNTHESIZER

    def test_analyze_to_reasoner(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Analyze the market trends")
        role, config = registry.resolve(intent)
        assert role == Role.REASONER

    def test_execute_to_agent(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Execute the migration")
        role, config = registry.resolve(intent)
        assert role == Role.AGENT

    def test_brainstorm_to_explorer(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Brainstorm ideas for the campaign")
        role, config = registry.resolve(intent)
        assert role == Role.EXPLORER

    def test_list_to_structurer(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("List all the items")
        role, config = registry.resolve(intent)
        assert role == Role.STRUCTURER

    def test_extract_to_structurer(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Extract all names from the text")
        role, config = registry.resolve(intent)
        assert role == Role.STRUCTURER

    def test_role_config_has_system_prompt(self):
        registry = RoleRegistry()
        registry.load()
        config = registry.get(Role.REASONER)
        assert config.system_prompt != ""
        assert "reasoner" in config.system_prompt.lower()

    def test_role_config_has_token_limits(self):
        registry = RoleRegistry()
        registry.load()
        config = registry.get(Role.AGENT)
        assert config.max_input_tokens > 0
        assert config.max_output_tokens > 0

    def test_legal_tag_overrides_to_narrator(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Summarize the statute")
        role, config = registry.resolve(intent, section_tags=["legal"])
        assert role == Role.NARRATOR

    def test_factual_tag_downgrades_explorer(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Write about the history of computing")
        role, config = registry.resolve(intent, section_tags=["factual"])
        assert role == Role.SYNTHESIZER

    def test_no_tags_keeps_default(self):
        registry = RoleRegistry()
        registry.load()
        intent = detect_intent("Summarize the document")
        role, _ = registry.resolve(intent)
        assert role == Role.SYNTHESIZER

    def test_all_roles_have_configs(self):
        registry = RoleRegistry()
        registry.load()
        for role in Role:
            config = registry.get(role)
            assert config is not None
            assert config.role == role
