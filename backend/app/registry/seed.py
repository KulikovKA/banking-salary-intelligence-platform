"""Idempotent POC seed for bank identity only; no tariff/source claims."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.registry.models import Bank

BANKS = (
    ("sber", "Сбер"),
    ("vtb", "ВТБ"),
    ("alfa", "Альфа-Банк"),
    ("kuban_credit", "Кубань Кредит"),
)


def seed_banks(session: Session) -> None:
    """Insert missing bank codes without changing names or inventing sources."""
    statement = insert(Bank).values(
        [{"code": code, "name": name, "active": True} for code, name in BANKS]
    )
    session.execute(statement.on_conflict_do_nothing(index_elements=[Bank.code]))
