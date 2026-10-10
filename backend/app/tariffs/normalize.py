"""Deterministic, side-effect-free normalization of raw tariff candidates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, TypeAlias, cast

from pydantic import TypeAdapter, ValidationError

from app.contracts.base import strict_decimal
from app.contracts.tariffs import (
    BooleanValue,
    Condition,
    CountValue,
    FormulaValue,
    IndividualValue,
    MoneyValue,
    PercentValue,
    RangeValue,
    TariffCandidate,
    TextValue,
)
from app.tariffs.metrics import get_metric

Raw: TypeAlias = Mapping[str, object]
_CONDITION_ADAPTER: TypeAdapter[Condition] = TypeAdapter(cast(Any, Condition))
_CURRENCY = re.compile(
    r"(?:\u20bd|\u0440\u0443\u0431(?:\.|\u043b\u0435\u0439|\u043b\u044f|\u043b\u044c)?|RUB)\s*$",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"%\s*$")


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Normalized DTO and diagnostics; raw date wording is retained verbatim."""

    candidate: TariffCandidate | None
    flags: tuple[str, ...]
    valid_from_text: str | None = None
    valid_to_text: str | None = None

    @property
    def ok(self) -> bool:
        return self.candidate is not None


def _flag(code: str) -> tuple[str, ...]:
    return (code,)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _decimal(value: object) -> Decimal:
    if isinstance(value, str):
        normalized = value.strip().replace("\u00a0", "").replace(" ", "")
        if normalized.count(",") == 1 and "." not in normalized:
            normalized = normalized.replace(",", ".")
        value = normalized
    return strict_decimal(value)


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("DATE_FORMAT_INVALID") from exc
    raise ValueError("DATE_FORMAT_INVALID")


def _normalize_value(
    raw: object,
    *,
    basis: object = None,
    currency: object = None,
    period: object = None,
) -> tuple[object | None, tuple[str, ...]]:
    if raw is None:
        return None, _flag("VALUE_UNKNOWN")
    if isinstance(raw, str):
        text = raw.strip()
        lowered = text.lower()
        if lowered in {
            "\u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e",
            "unknown",
            "\u043d/\u0434",
            "n/a",
        }:
            return None, _flag("VALUE_UNKNOWN")
        if "\u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e" in lowered or lowered in {
            "free",
            "\u0431\u0435\u0437 \u043a\u043e\u043c\u0438\u0441\u0441\u0438\u0438",
        }:
            if currency != "RUB":
                return None, _flag("CURRENCY_UNKNOWN")
            flags = ("CONDITIONS_UNPARSED",) if "\u043f\u0440\u0438" in lowered else ()
            return {
                "kind": "money",
                "amount": Decimal(0),
                "currency": currency,
                "conditions_text": text,
            }, flags
        if _PERCENT.search(text):
            if not isinstance(basis, str) or not basis:
                return None, _flag("PERCENT_BASIS_UNKNOWN")
            return {
                "kind": "percent",
                "amount": _decimal(_PERCENT.sub("", text)),
                "basis": basis,
                "period": period,
            }, ()
        if _CURRENCY.search(text):
            return {
                "kind": "money",
                "amount": _decimal(_CURRENCY.sub("", text)),
                "currency": "RUB",
                "period": period,
            }, ()
        if lowered.startswith(
            (
                "\u0438\u043d\u0434\u0438\u0432\u0438\u0434\u0443\u0430\u043b\u044c\u043d",
                "\u043f\u043e \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d",
                "\u043f\u043e \u0437\u0430\u043f\u0440\u043e\u0441\u0443",
            )
        ):
            return {"kind": "individual", "text_value": text}, ()
        return None, _flag("VALUE_UNIT_UNKNOWN")
    if not isinstance(raw, Mapping):
        return None, _flag("VALUE_SHAPE_INVALID")

    data = dict(raw)
    kind = data.get("kind")
    raw_amount = data.get("amount")
    if kind in {"money", "percent"} and isinstance(raw_amount, str):
        text = raw_amount.strip()
        has_percent = bool(_PERCENT.search(text))
        has_currency = bool(_CURRENCY.search(text))
        if has_percent:
            if kind != "percent":
                return None, _flag("VALUE_UNIT_KIND_CONFLICT")
            data["amount"] = _decimal(_PERCENT.sub("", text))
        elif has_currency:
            if kind != "money":
                return None, _flag("VALUE_UNIT_KIND_CONFLICT")
            data["amount"] = _decimal(_CURRENCY.sub("", text))
            data.setdefault("currency", "RUB")
        else:
            data["amount"] = _decimal(text)
    elif kind == "range":
        for bound in ("lower", "upper"):
            if isinstance(data.get(bound), str):
                data[bound] = _decimal(data[bound])
    elif kind == "individual":
        if not isinstance(data.get("text_value"), str) or not data["text_value"].strip():
            return None, _flag("INDIVIDUAL_TEXT_REQUIRED")
        data["text_value"] = data["text_value"].strip()
    elif kind not in {
        "money",
        "percent",
        "count",
        "boolean",
        "text",
        "range",
        "formula",
        "individual",
    }:
        return None, _flag("VALUE_KIND_UNKNOWN")
    return data, ()


def normalize_candidate(raw: Raw) -> NormalizationResult:
    """Normalize an untrusted mapping into the frozen candidate contract.

    No scope, payer, operation, unit, condition, region, or date is inferred. A
    malformed or unknown value returns diagnostics and never a zero-valued fee.
    ``valid_to_inclusive`` must be explicit before an end date is advanced.
    """

    data = dict(raw)
    flags: list[str] = []
    valid_from_text = _text(data.get("valid_from_text"))
    valid_to_text = _text(data.get("valid_to_text"))

    payer = data.get("payer")
    if payer not in {"employer", "employee"}:
        return NormalizationResult(None, _flag("PAYER_UNKNOWN"), valid_from_text, valid_to_text)
    if not isinstance(data.get("operation"), str) or not cast(str, data["operation"]).strip():
        return NormalizationResult(None, _flag("OPERATION_UNKNOWN"), valid_from_text, valid_to_text)
    data["operation"] = cast(str, data["operation"]).strip()

    try:
        value, value_flags = _normalize_value(
            data.get("value"),
            basis=data.get("basis"),
            currency=data.get("currency"),
            period=data.get("period"),
        )
    except (ValueError, InvalidOperation):
        return NormalizationResult(None, _flag("VALUE_INVALID"), valid_from_text, valid_to_text)
    flags.extend(value_flags)
    if value is None:
        return NormalizationResult(
            None, tuple(dict.fromkeys(flags)), valid_from_text, valid_to_text
        )
    if isinstance(value, Mapping) and isinstance(value.get("conditions_text"), str):
        data.setdefault("conditions_text", value["conditions_text"])
        value = {key: item for key, item in value.items() if key != "conditions_text"}
    if "CONDITIONS_UNPARSED" in flags:
        data["requires_manual_interpretation"] = True
    data["value"] = value

    conditions = data.get("conditions")
    if conditions is not None:
        try:
            data["conditions"] = _CONDITION_ADAPTER.validate_python(conditions)
        except ValidationError:
            flags.append("CONDITION_AST_INVALID")
            return NormalizationResult(
                None, tuple(dict.fromkeys(flags)), valid_from_text, valid_to_text
            )

    condition_text = data.get("conditions_text")
    if isinstance(condition_text, str) and condition_text.strip():
        data["conditions_text"] = condition_text.strip()
        unconditional_free = condition_text.strip().lower() in {
            "free",
            "\u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e",
            "\u0431\u0435\u0437 \u043a\u043e\u043c\u0438\u0441\u0441\u0438\u0438",
        }
        if conditions is None and not unconditional_free:
            flags.append("CONDITIONS_UNPARSED")
            data["requires_manual_interpretation"] = True

    try:
        valid_from = _parse_date(data.get("valid_from"))
        valid_to = _parse_date(data.get("valid_to"))
        inclusive = data.get("valid_to_inclusive", False)
        if not isinstance(inclusive, bool):
            raise ValueError("DATE_INCLUSIVE_FLAG_INVALID")
        if inclusive and valid_to is None:
            raise ValueError("DATE_END_REQUIRED_FOR_INCLUSIVE_FLAG")
        if valid_to is not None and inclusive:
            valid_to += timedelta(days=1)
        data["valid_from"] = valid_from
        data["valid_to"] = valid_to
    except (ValueError, OverflowError):
        return NormalizationResult(
            None, tuple(dict.fromkeys((*flags, "DATE_INVALID"))), valid_from_text, valid_to_text
        )

    if valid_from is None:
        data["effective_date_status"] = "unknown"
        flags.append("DATE_UNKNOWN" if valid_to is None else "DATE_START_UNKNOWN")
    elif data.get("effective_date_status", "explicit") == "unknown":
        flags.append("DATE_STATUS_CONFLICT")
        return NormalizationResult(
            None, tuple(dict.fromkeys(flags)), valid_from_text, valid_to_text
        )
    else:
        data["effective_date_status"] = data.get("effective_date_status", "explicit")

    for raw_field in (
        "valid_from_text",
        "valid_to_text",
        "valid_to_inclusive",
        "basis",
        "currency",
    ):
        data.pop(raw_field, None)
    existing_flags = data.get("validation_flags", ())
    if not isinstance(existing_flags, (tuple, list)) or not all(
        isinstance(flag, str) for flag in existing_flags
    ):
        existing_flags = ()
    data["validation_flags"] = tuple(dict.fromkeys((*existing_flags, *flags)))
    try:
        candidate = TariffCandidate.model_validate(data)
    except ValidationError as exc:
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"])
            code = str(error["type"]).upper().replace(".", "_")
            flags.append(f"CANDIDATE_INVALID:{loc}:{code}")
        return NormalizationResult(
            None, tuple(dict.fromkeys(flags)), valid_from_text, valid_to_text
        )

    metric = get_metric(candidate.metric_code)
    candidate_value = candidate.value
    unit = getattr(candidate_value, "unit", None)
    if isinstance(candidate_value, MoneyValue):
        unit = "currency"
    elif isinstance(candidate_value, PercentValue):
        unit = "percent"
    elif isinstance(candidate_value, CountValue):
        unit = candidate_value.unit
    elif isinstance(candidate_value, RangeValue):
        unit = candidate_value.unit
    elif isinstance(candidate_value, FormulaValue):
        unit = "currency" if candidate_value.currency else "percent"
    elif isinstance(candidate_value, BooleanValue):
        unit = "boolean"
    elif isinstance(candidate_value, TextValue):
        unit = "text"
    if metric is None:
        flags.append("METRIC_UNKNOWN")
    elif (
        candidate_value.kind not in metric.allowed_kinds
        or (unit not in metric.allowed_units and not isinstance(candidate_value, IndividualValue))
        or (
            isinstance(candidate_value, (MoneyValue, RangeValue, FormulaValue))
            and getattr(candidate_value, "currency", None) not in {None, "RUB"}
        )
        or candidate.payer not in metric.payer
        or candidate.operation not in metric.operation
    ):
        flags.append("METRIC_SEMANTICS_MISMATCH")
    if any(flag.startswith("METRIC_") for flag in flags):
        return NormalizationResult(
            None, tuple(dict.fromkeys(flags)), valid_from_text, valid_to_text
        )

    return NormalizationResult(
        candidate, tuple(dict.fromkeys(flags)), valid_from_text, valid_to_text
    )


__all__ = ["NormalizationResult", "normalize_candidate"]
