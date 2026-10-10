"""Provider-neutral LLM request validation and safe renderer boundaries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.contracts.llm import ExplainResult, IntentResult, LLMRequest

_ALLOWED_TEMPLATES = frozenset({"claim_fact", "claim_comparison", "claim_absence"})


class OutputValidationError(ValueError):
    """The generated structure violates the request or backend allowlists."""


def validate_output(request: LLMRequest, payload: object) -> dict[str, object]:
    """Validate structured output and constrain explain output to backend inputs.

    The schema supplied by the caller declares the output shape; Pydantic's frozen
    SNAP-01 result DTOs then enforce the wire contract. Explain IDs and templates
    are treated as untrusted and intersected with backend-owned allowlists.
    """
    try:
        if request.purpose == "intent":
            parsed = IntentResult.model_validate(payload)
            _validate_declared_schema(request.output_schema, payload)
            return parsed.model_dump(mode="json", exclude={"schema_version"})

        parsed_explain = ExplainResult.model_validate(payload)
        _validate_declared_schema(request.output_schema, payload)
        allowed_ids = _uuid_allowlist(request.output_schema.get("allowed_claim_ids"))
        allowed_templates = request.output_schema.get("allowed_templates")
        if not isinstance(allowed_templates, list) or not all(
            isinstance(item, str) for item in allowed_templates
        ):
            raise OutputValidationError("EXPLAIN_ALLOWLIST_MISSING")
        templates = _ALLOWED_TEMPLATES.intersection(allowed_templates)
        if any(item not in allowed_ids for item in parsed_explain.ordered_claim_ids):
            raise OutputValidationError("UNKNOWN_CLAIM_ID")
        if any(
            claim_id not in allowed_ids or template not in templates
            for claim_id, template in parsed_explain.template_by_claim.items()
        ):
            raise OutputValidationError("UNSUPPORTED_RENDER_TEMPLATE")
        if not set(parsed_explain.template_by_claim) <= set(parsed_explain.ordered_claim_ids):
            raise OutputValidationError("TEMPLATE_FOR_UNORDERED_CLAIM")
        return parsed_explain.model_dump(mode="json", exclude={"schema_version"})
    except (ValidationError, TypeError, ValueError) as exc:
        if isinstance(exc, OutputValidationError):
            raise
        raise OutputValidationError("INVALID_STRUCTURED_OUTPUT") from exc


def _uuid_allowlist(value: object) -> frozenset[UUID]:
    if not isinstance(value, list):
        raise OutputValidationError("EXPLAIN_ALLOWLIST_MISSING")
    try:
        return frozenset(UUID(item) for item in value if isinstance(item, str))
    except ValueError as exc:
        raise OutputValidationError("EXPLAIN_ALLOWLIST_INVALID") from exc


def _validate_declared_schema(schema: dict[str, Any], payload: object) -> None:
    """Enforce common JSON Schema object/required/property/enum constraints."""
    if not isinstance(payload, dict) or schema.get("type") != "object":
        raise OutputValidationError("OUTPUT_SCHEMA_MISMATCH")
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    if not isinstance(required, list) or not isinstance(properties, dict):
        raise OutputValidationError("OUTPUT_SCHEMA_INVALID")
    if any(key not in payload for key in required):
        raise OutputValidationError("OUTPUT_SCHEMA_REQUIRED_FIELD_MISSING")
    if schema.get("additionalProperties") is False and any(
        key not in properties for key in payload
    ):
        raise OutputValidationError("OUTPUT_SCHEMA_EXTRA_FIELD")
    for key, value in payload.items():
        rule = properties.get(key)
        if isinstance(rule, dict) and "enum" in rule and value not in rule["enum"]:
            raise OutputValidationError("OUTPUT_SCHEMA_ENUM_INVALID")
