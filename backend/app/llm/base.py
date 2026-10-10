"""Provider-neutral LLM request validation and safe renderer boundaries."""

from __future__ import annotations

import json
import math
import re
from datetime import date
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
        # Reject Python-only values and non-finite numbers, including JSON NaN.
        json.dumps(payload, allow_nan=False)
        if request.purpose == "intent":
            parsed = IntentResult.model_validate(payload)
            _validate_declared_schema(request.output_schema, payload)
            normalized = parsed.model_dump(mode="json", exclude={"schema_version"})
            _validate_declared_schema(request.output_schema, normalized)
            return normalized

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
        if len(set(parsed_explain.ordered_claim_ids)) != len(parsed_explain.ordered_claim_ids):
            raise OutputValidationError("DUPLICATE_CLAIM_ID")
        if any(
            claim_id not in allowed_ids or template not in templates
            for claim_id, template in parsed_explain.template_by_claim.items()
        ):
            raise OutputValidationError("UNSUPPORTED_RENDER_TEMPLATE")
        if not set(parsed_explain.template_by_claim) <= set(parsed_explain.ordered_claim_ids):
            raise OutputValidationError("TEMPLATE_FOR_UNORDERED_CLAIM")
        normalized = parsed_explain.model_dump(mode="json", exclude={"schema_version"})
        _validate_declared_schema(request.output_schema, normalized)
        return normalized
    except (ValidationError, TypeError, ValueError, re.error) as exc:
        if isinstance(exc, OutputValidationError):
            raise
        raise OutputValidationError("INVALID_STRUCTURED_OUTPUT") from exc


def _uuid_allowlist(value: object) -> frozenset[UUID]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise OutputValidationError("EXPLAIN_ALLOWLIST_MISSING")
    try:
        return frozenset(UUID(item) for item in value if isinstance(item, str))
    except ValueError as exc:
        raise OutputValidationError("EXPLAIN_ALLOWLIST_INVALID") from exc


def _validate_declared_schema(schema: dict[str, object], payload: object) -> None:
    """Validate the bounded subset used by intent/explain schemas, fail closed.

    Supports the frozen DTO-generated schemas and narrower backend constraints.
    Unknown keywords are rejected rather than silently ignored. This helper is
    not a general JSON Schema implementation and never resolves remote refs.
    The two allowlist annotations are backend inputs, not generated model data.
    """
    if schema.get("type") != "object":
        raise OutputValidationError("OUTPUT_SCHEMA_MISMATCH")
    _validate_node(schema, payload, schema, 0)


def _validate_node(schema: object, value: object, root: dict[str, object], depth: int) -> None:
    if depth > 20:
        raise OutputValidationError("OUTPUT_SCHEMA_DEPTH_EXCEEDED")
    if schema is True:
        return
    if schema is False:
        raise OutputValidationError("OUTPUT_SCHEMA_MISMATCH")
    if not isinstance(schema, dict):
        raise OutputValidationError("OUTPUT_SCHEMA_INVALID")
    supported = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "propertyNames",
        "items",
        "enum",
        "const",
        "anyOf",
        "$ref",
        "$defs",
        "title",
        "description",
        "default",
        "format",
        "pattern",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minimum",
        "maximum",
        "minProperties",
        "maxProperties",
    }
    if depth == 0:
        supported.update({"allowed_claim_ids", "allowed_templates"})
    if not set(schema) <= supported:
        raise OutputValidationError("OUTPUT_SCHEMA_KEYWORD_UNSUPPORTED")
    ref = schema.get("$ref")
    if ref is not None:
        definitions = root.get("$defs")
        if (
            not isinstance(ref, str)
            or not ref.startswith("#/$defs/")
            or not isinstance(definitions, dict)
            or ref[8:] not in definitions
        ):
            raise OutputValidationError("OUTPUT_SCHEMA_REF_UNSUPPORTED")
        _validate_node(definitions[ref[8:]], value, root, depth + 1)
    if "anyOf" in schema:
        alternatives = schema["anyOf"]
        if not isinstance(alternatives, list) or not alternatives:
            raise OutputValidationError("OUTPUT_SCHEMA_INVALID")
        for alternative in alternatives:
            try:
                _validate_node(alternative, value, root, depth + 1)
                break
            except OutputValidationError:
                continue
        else:
            raise OutputValidationError("OUTPUT_SCHEMA_MISMATCH")
    if "const" in schema and value != schema["const"]:
        raise OutputValidationError("OUTPUT_SCHEMA_CONST_INVALID")
    if "enum" in schema:
        options = schema["enum"]
        if not isinstance(options, list) or value not in options:
            raise OutputValidationError("OUTPUT_SCHEMA_ENUM_INVALID")
    kind = schema.get("type")
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in (int, float),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if kind is not None and (not isinstance(kind, str) or not matches.get(kind, False)):
        raise OutputValidationError("OUTPUT_SCHEMA_TYPE_INVALID")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise OutputValidationError("OUTPUT_SCHEMA_INVALID")
        if not all(isinstance(key, str) and key in value for key in required):
            raise OutputValidationError("OUTPUT_SCHEMA_REQUIRED_FIELD_MISSING")
        _check_bounds(schema, len(value), "minProperties", "maxProperties")
        for key, item in value.items():
            if not isinstance(key, str):
                raise OutputValidationError("OUTPUT_SCHEMA_KEY_INVALID")
            if "propertyNames" in schema:
                _validate_node(schema["propertyNames"], key, root, depth + 1)
            _validate_node(
                properties.get(key, schema.get("additionalProperties", True)),
                item,
                root,
                depth + 1,
            )
    elif isinstance(value, list):
        _check_bounds(schema, len(value), "minItems", "maxItems")
        if schema.get("uniqueItems") is True and any(
            item in value[:index] for index, item in enumerate(value)
        ):
            raise OutputValidationError("OUTPUT_SCHEMA_DUPLICATE_ITEM")
        for item in value:
            _validate_node(schema.get("items", True), item, root, depth + 1)
    elif isinstance(value, str):
        _check_bounds(schema, len(value), "minLength", "maxLength")
        if "pattern" in schema:
            pattern = schema["pattern"]
            if not isinstance(pattern, str) or re.search(pattern, value) is None:
                raise OutputValidationError("OUTPUT_SCHEMA_PATTERN_INVALID")
        format_name = schema.get("format")
        if format_name == "uuid":
            UUID(value)
        elif format_name == "date":
            date.fromisoformat(value)
        elif format_name is not None:
            raise OutputValidationError("OUTPUT_SCHEMA_FORMAT_UNSUPPORTED")
    elif type(value) in (int, float) and isinstance(value, int | float):
        if not math.isfinite(value):
            raise OutputValidationError("OUTPUT_SCHEMA_NONFINITE_NUMBER")
        _check_bounds(schema, value, "minimum", "maximum")


def _check_bounds(schema: dict[str, object], value: int | float, lower: str, upper: str) -> None:
    for keyword in (lower, upper):
        if keyword in schema:
            bound = schema[keyword]
            if not isinstance(bound, int | float) or isinstance(bound, bool):
                raise OutputValidationError("OUTPUT_SCHEMA_BOUND_INVALID")
            if (keyword == lower and value < bound) or (keyword == upper and value > bound):
                raise OutputValidationError("OUTPUT_SCHEMA_BOUND_EXCEEDED")
