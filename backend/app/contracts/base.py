"""Shared strict primitives for versioned snapshot DTOs."""

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

BankCode = Literal["sber", "vtb", "alfa", "kuban_credit"]
BANK_CODES: tuple[str, ...] = ("sber", "vtb", "alfa", "kuban_credit")
CorpusKind = Literal["synthetic", "real"]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1, max_length=10_000)]


class ContractModel(BaseModel):
    """Base for immutable wire contracts; unknown fields are always errors."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal[1] = 1


def strict_decimal(value: object) -> Decimal:
    """Parse decimal strings and trusted Decimal values, never binary floats."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("DECIMAL_MUST_NOT_BE_FLOAT")
    if not isinstance(value, (str, Decimal)):
        raise ValueError("DECIMAL_STRING_REQUIRED")
    if isinstance(value, str) and not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value
    ):
        raise ValueError("DECIMAL_STRING_INVALID")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("DECIMAL_INVALID") from exc
    if not number.is_finite():
        raise ValueError("DECIMAL_MUST_BE_FINITE")
    if len(number.as_tuple().digits) > 28:
        raise ValueError("DECIMAL_PRECISION_EXCEEDED")
    return number


def require_aware_utc(value: datetime) -> datetime:
    """Require an explicit offset and normalize instants to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC_OFFSET_REQUIRED")
    return value.astimezone(UTC)


class DecimalStringModel(ContractModel):
    @field_serializer(
        "amount", "lower", "upper", "payroll_total", "transfer_amount", check_fields=False
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")


class UuidModel(ContractModel):
    id: UUID


__all__ = [
    "BankCode",
    "ContractModel",
    "CorpusKind",
    "DecimalStringModel",
    "NonEmpty",
    "Sha256",
    "UuidModel",
    "require_aware_utc",
    "strict_decimal",
]
