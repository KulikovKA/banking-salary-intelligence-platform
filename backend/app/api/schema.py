"""Correct OpenAPI's Decimal input metadata to the frozen string-only validators."""

from typing import Any


def wire_schema(openapi: dict[str, Any]) -> dict[str, Any]:
    # Pydantic's Decimal validation schema advertises numbers, although SNAP-01's
    # before validators reject integers/floats. Correct documentation, not validation.
    schemas = openapi["components"]["schemas"]
    for name, fields in {
        "Scenario-Input": ("payroll_total", "transfer_amount"),
    }.items():
        if name not in schemas:
            continue
        for field in fields:
            value = schemas[name]["properties"][field]
            value["anyOf"] = [item for item in value["anyOf"] if item.get("type") != "number"]
    return openapi
