"""Cached Action Plan Engine (Patent XIII, XIV).

AI agents reason through a task once, and the execution plan is cached.
Subsequent executions with different parameters replay the plan
deterministically -- zero LLM reasoning.
"""

import hashlib
import hmac
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in an action plan."""

    tool: str
    parameters: dict
    output_binding: str = ""


@dataclass
class ActionPlan:
    """A cached, replayable action plan."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent_key: str = ""
    intent_raw: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    parameter_slots: dict = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    source_manifest: list[dict] = field(default_factory=list)
    hmac_signature: str = ""
    execution_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def compute_intent_key(intent: str, filters: dict | None = None) -> str:
    """Compute SHA-256 key from normalized intent + filters."""
    normalized = re.sub(r"[^\w\s]", " ", intent.lower().strip())
    tokens = sorted(set(normalized.split()))
    parts = [" ".join(tokens)]
    if filters:
        for k in sorted(filters):
            if filters[k]:
                parts.append(f"{k}:{filters[k]}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def sign_plan(plan: ActionPlan, secret: str) -> str:
    """Generate HMAC-SHA256 signature for plan integrity verification."""
    payload = json.dumps(
        {
            "id": plan.id,
            "intent_key": plan.intent_key,
            "steps": [
                {"tool": s.tool, "parameters": s.parameters, "output_binding": s.output_binding} for s in plan.steps
            ],
            "allowed_tools": plan.allowed_tools,
            "parameter_slots": plan.parameter_slots,
        },
        sort_keys=True,
    )
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_plan(plan: ActionPlan, secret: str) -> bool:
    """Verify HMAC signature matches plan content."""
    expected = sign_plan(plan, secret)
    return hmac.compare_digest(plan.hmac_signature, expected)


def validate_parameters(plan: ActionPlan, params: dict) -> list[str]:
    """Validate parameters against plan's typed constraints.

    Returns list of error messages (empty if valid).
    """
    errors = []
    for slot_name, constraints in plan.parameter_slots.items():
        if constraints.get("required") and slot_name not in params:
            errors.append(f"Missing required parameter: {slot_name}")
            continue

        if slot_name in params:
            value = params[slot_name]
            expected_type = constraints.get("type", "string")
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Parameter {slot_name} must be a string")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Parameter {slot_name} must be an integer")

            pattern = constraints.get("pattern")
            if pattern and isinstance(value, str) and not re.match(pattern, value):
                errors.append(f"Parameter {slot_name} doesn't match pattern {pattern}")

    return errors


def inject_parameters(step: PlanStep, params: dict) -> dict:
    """Inject parameters into a step's parameter template.

    Replaces {param_name} placeholders with actual values.
    """
    resolved = {}
    for key, value in step.parameters.items():
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            param_name = value[1:-1]
            if param_name in params:
                resolved[key] = params[param_name]
            else:
                resolved[key] = value  # Leave unresolved
        else:
            resolved[key] = value
    return resolved


def execute_plan(
    plan: ActionPlan,
    params: dict,
    tool_executor: Any,
    secret: str,
) -> dict:
    """Execute a cached action plan with new parameters.

    1. Verify HMAC integrity
    2. Validate parameters
    3. Execute each step deterministically
    4. Return results

    Returns execution record.
    """
    execution_id = str(uuid.uuid4())

    # Step 1: Verify integrity
    if not verify_plan(plan, secret):
        return {"error": "Plan integrity check failed -- HMAC mismatch", "execution_id": execution_id}

    # Step 2: Validate parameters
    errors = validate_parameters(plan, params)
    if errors:
        return {"error": "Parameter validation failed", "details": errors, "execution_id": execution_id}

    # Step 3: Execute steps
    results: dict = {}
    for i, step in enumerate(plan.steps):
        # Check tool is allowed
        if step.tool in plan.forbidden_tools:
            return {"error": f"Step {i}: tool '{step.tool}' is forbidden", "execution_id": execution_id}
        if plan.allowed_tools and step.tool not in plan.allowed_tools:
            return {"error": f"Step {i}: tool '{step.tool}' not in allowed list", "execution_id": execution_id}

        # Inject parameters
        resolved_params = inject_parameters(step, {**params, **results})

        # Execute
        try:
            result = tool_executor(step.tool, resolved_params)
            if step.output_binding:
                results[step.output_binding] = result
        except Exception as e:
            return {"error": f"Step {i} ({step.tool}) failed: {str(e)}", "execution_id": execution_id}

    plan.execution_count += 1

    return {
        "execution_id": execution_id,
        "plan_id": plan.id,
        "results": results,
        "steps_executed": len(plan.steps),
        "parameters_used": params,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
