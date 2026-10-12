"""Fail-closed minimization harness; arbitrary free text never reaches a provider."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.contracts.api import QuestionRequest
from app.contracts.base import BankCode

_BANKS: dict[str, BankCode] = {
    "сбера": "sber",
    "сбер": "sber",
    "втб": "vtb",
    "альфа-банка": "alfa",
    "альфа-банк": "alfa",
    "кубань кредит": "kuban_credit",
}
_BANK = "(?:" + "|".join(re.escape(item) for item in _BANKS) + ")"


@dataclass(frozen=True)
class MinimizedQuestion:
    """Canonical labels only, or a local clarification with no outgoing payload."""

    payload: str | None
    clarification: str | None = None


def minimize_question(request: QuestionRequest) -> MinimizedQuestion:
    """Recognize a small closed grammar, never assert regex redaction is safe.

    Scenario fields and filter strings are deliberately excluded: frozen Scenario
    permits arbitrary strings (including names/secrets). Unsupported wording must
    be clarified locally until the full SNAP-14 input pipeline is integrated.
    """
    question = request.question.strip().lower().rstrip("? .")
    direct = re.fullmatch(rf"сколько стоит зарплатный проект (?P<bank>{_BANK})", question)
    pair = re.fullmatch(rf"чем (?P<left>{_BANK}) выгоднее (?P<right>{_BANK})", question)
    intent = "clarify"
    banks: list[BankCode] = []
    if direct:
        intent, banks = "facts", [_BANKS[direct["bank"]]]
    elif pair and pair["left"] != pair["right"]:
        intent, banks = "compare", [_BANKS[pair["left"]], _BANKS[pair["right"]]]
        if len(set(banks)) != 2:
            return MinimizedQuestion(None, "Выберите два разных банка.")
    elif question == "на основании какого документа указана эта комиссия":
        intent = "documents"
    elif question != "какой банк самый лучший":
        return MinimizedQuestion(
            None,
            "Уточните банки и критерий через структурированные поля, "
            "без ФИО, реквизитов и зарплат отдельных сотрудников.",
        )
    return MinimizedQuestion(
        json.dumps(
            {
                "intent_hint": intent,
                "bank_codes": banks,
                "metric_codes": ["payroll_credit_fee"] if intent != "clarify" else [],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
