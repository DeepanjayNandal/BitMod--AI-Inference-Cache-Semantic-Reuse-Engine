"""Tests for the cached action plan engine: HMAC signing, validation, parameter injection, execution."""

import pytest

from bitmod.action_plans import (
    ActionPlan,
    PlanStep,
    compute_intent_key,
    execute_plan,
    inject_parameters,
    sign_plan,
    validate_parameters,
    verify_plan,
)


SECRET = "test-secret-key-for-hmac"


class TestComputeIntentKey:
    """Test intent key generation."""

    def test_deterministic(self):
        """Same intent produces the same key."""
        k1 = compute_intent_key("file a compliance report")
        k2 = compute_intent_key("file a compliance report")
        assert k1 == k2
        assert len(k1) == 64  # SHA-256 hex

    def test_case_insensitive(self):
        """Intent key is case-insensitive."""
        k1 = compute_intent_key("File A Report")
        k2 = compute_intent_key("file a report")
        assert k1 == k2

    def test_filters_affect_key(self):
        """Different filters produce different keys."""
        k1 = compute_intent_key("report", filters={"region": "US"})
        k2 = compute_intent_key("report", filters={"region": "EU"})
        assert k1 != k2


class TestHMACSigningAndVerification:
    """Test plan signing and verification."""

    def _make_plan(self):
        """Create a simple test plan."""
        return ActionPlan(
            id="plan-001",
            intent_key="key-001",
            steps=[
                PlanStep(tool="search_data", parameters={"query": "{search_term}"}, output_binding="results"),
                PlanStep(tool="get_section", parameters={"section_id": "{section_id}"}),
            ],
            allowed_tools=["search_data", "get_section"],
            parameter_slots={
                "search_term": {"type": "string", "required": True},
                "section_id": {"type": "string", "required": False},
            },
        )

    def test_sign_produces_hex_string(self):
        """Signing a plan produces a 64-char hex string."""
        plan = self._make_plan()
        sig = sign_plan(plan, SECRET)
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_verify_valid_signature(self):
        """A correctly signed plan passes verification."""
        plan = self._make_plan()
        plan.hmac_signature = sign_plan(plan, SECRET)
        assert verify_plan(plan, SECRET) is True

    def test_verify_tampered_plan_fails(self):
        """Modifying the plan after signing causes verification to fail."""
        plan = self._make_plan()
        plan.hmac_signature = sign_plan(plan, SECRET)
        plan.steps.append(PlanStep(tool="malicious_tool", parameters={}))
        assert verify_plan(plan, SECRET) is False

    def test_verify_wrong_secret_fails(self):
        """Verification with a different secret fails."""
        plan = self._make_plan()
        plan.hmac_signature = sign_plan(plan, SECRET)
        assert verify_plan(plan, "wrong-secret") is False


class TestValidateParameters:
    """Test parameter validation against plan constraints."""

    def test_valid_params(self):
        """Valid parameters produce no errors."""
        plan = ActionPlan(
            parameter_slots={
                "name": {"type": "string", "required": True},
                "count": {"type": "integer", "required": False},
            },
        )
        errors = validate_parameters(plan, {"name": "Alice", "count": 5})
        assert errors == []

    def test_missing_required_param(self):
        """Missing a required parameter produces an error."""
        plan = ActionPlan(
            parameter_slots={"name": {"type": "string", "required": True}},
        )
        errors = validate_parameters(plan, {})
        assert len(errors) == 1
        assert "Missing required" in errors[0]

    def test_wrong_type_string(self):
        """Passing int where string expected produces an error."""
        plan = ActionPlan(
            parameter_slots={"name": {"type": "string", "required": True}},
        )
        errors = validate_parameters(plan, {"name": 123})
        assert any("must be a string" in e for e in errors)

    def test_wrong_type_integer(self):
        """Passing string where integer expected produces an error."""
        plan = ActionPlan(
            parameter_slots={"count": {"type": "integer", "required": True}},
        )
        errors = validate_parameters(plan, {"count": "five"})
        assert any("must be an integer" in e for e in errors)

    def test_pattern_mismatch(self):
        """Value not matching regex pattern produces an error."""
        plan = ActionPlan(
            parameter_slots={
                "code": {"type": "string", "required": True, "pattern": r"^[A-Z]{2}$"},
            },
        )
        errors = validate_parameters(plan, {"code": "california"})
        assert any("pattern" in e for e in errors)

    def test_pattern_match(self):
        """Value matching regex pattern produces no error."""
        plan = ActionPlan(
            parameter_slots={
                "code": {"type": "string", "required": True, "pattern": r"^[A-Z]{2}$"},
            },
        )
        errors = validate_parameters(plan, {"code": "CA"})
        assert errors == []


class TestInjectParameters:
    """Test parameter injection into step templates."""

    def test_placeholder_replaced(self):
        """Placeholders like {name} are replaced with actual values."""
        step = PlanStep(tool="search", parameters={"query": "{search_term}", "limit": 10})
        result = inject_parameters(step, {"search_term": "employment law"})
        assert result["query"] == "employment law"
        assert result["limit"] == 10

    def test_unresolved_placeholder_left(self):
        """Placeholders without matching params are left as-is."""
        step = PlanStep(tool="search", parameters={"query": "{missing_param}"})
        result = inject_parameters(step, {})
        assert result["query"] == "{missing_param}"


class TestExecutePlan:
    """Test full plan execution flow."""

    def _make_signed_plan(self):
        """Create and sign a test plan."""
        plan = ActionPlan(
            id="exec-001",
            intent_key="exec-key",
            steps=[
                PlanStep(tool="search_data", parameters={"query": "{term}"}, output_binding="search_result"),
            ],
            allowed_tools=["search_data"],
            parameter_slots={"term": {"type": "string", "required": True}},
        )
        plan.hmac_signature = sign_plan(plan, SECRET)
        return plan

    def test_successful_execution(self):
        """Properly signed plan with valid params executes all steps."""
        plan = self._make_signed_plan()

        def mock_executor(tool, params):
            return {"matches": 3}

        result = execute_plan(plan, {"term": "employment"}, mock_executor, SECRET)
        assert "error" not in result
        assert result["steps_executed"] == 1
        assert result["results"]["search_result"] == {"matches": 3}
        assert plan.execution_count == 1

    def test_hmac_failure_blocks_execution(self):
        """Tampered plan (bad HMAC) is rejected."""
        plan = self._make_signed_plan()
        plan.hmac_signature = "tampered_signature"

        result = execute_plan(plan, {"term": "test"}, lambda t, p: None, SECRET)
        assert "error" in result
        assert "HMAC" in result["error"]

    def test_validation_failure_blocks_execution(self):
        """Invalid parameters block execution."""
        plan = self._make_signed_plan()

        result = execute_plan(plan, {}, lambda t, p: None, SECRET)  # missing required 'term'
        assert "error" in result
        assert "validation" in result["error"].lower()

    def test_forbidden_tool_blocks_step(self):
        """Steps using forbidden tools are rejected."""
        plan = ActionPlan(
            id="forb-001",
            steps=[PlanStep(tool="dangerous_tool", parameters={})],
            forbidden_tools=["dangerous_tool"],
            allowed_tools=["dangerous_tool"],  # allowed but also forbidden
        )
        plan.hmac_signature = sign_plan(plan, SECRET)

        result = execute_plan(plan, {}, lambda t, p: None, SECRET)
        assert "error" in result
        assert "forbidden" in result["error"]

    def test_tool_not_in_allowed_list(self):
        """Steps with tools not in allowed_tools are rejected."""
        plan = ActionPlan(
            id="unauth-001",
            steps=[PlanStep(tool="unknown_tool", parameters={})],
            allowed_tools=["search_data"],
        )
        plan.hmac_signature = sign_plan(plan, SECRET)

        result = execute_plan(plan, {}, lambda t, p: None, SECRET)
        assert "error" in result
        assert "not in allowed" in result["error"]

    def test_step_exception_handled(self):
        """Exceptions in tool execution are caught and returned as errors."""
        plan = self._make_signed_plan()

        def failing_executor(tool, params):
            raise RuntimeError("Tool crashed")

        result = execute_plan(plan, {"term": "test"}, failing_executor, SECRET)
        assert "error" in result
        assert "failed" in result["error"]
