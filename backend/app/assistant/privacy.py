"""Fail-closed domain minimization; arbitrary chat never reaches a provider."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal

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
    scenario_patch: dict[str, object] | None = None


def minimize_question(request: QuestionRequest) -> MinimizedQuestion:
    """Canonicalize admitted wording, never assert regex redaction is safe.

    Scenario fields and filter strings are deliberately excluded: frozen Scenario
    permits arbitrary strings (including names/secrets). Local domain vocabulary
    and aggregate parsing extend the original grammar; other wording is clarified.
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
        return _minimize_domain_question(request)
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


# Every token must be accounted for. These are domain concepts, not a blacklist
# or a claim that redaction makes arbitrary text safe. No original token is sent.
_WORDS = frozenset(
    "сколько стоит стоимость зарплатный зарплатного проект проекта проекты "
    "сравни сравнить сравнение чем выгоднее какой банк банки лучше лучший всего "
    "по комиссия комиссиям комиссию комиссии тариф тарифы покажи документ "
    "документы подтверждающий подтверждает на основании какого указана эта "
    "и для у нас сотрудников зарплатный фонд рублей рубля руб в месяц месячный "
    "сбер сбера втб альфа-банк альфа-банка кубань кредит обслуживание счета счёта "
    "краснодарский край пожалуйста".split()
)
_CLARIFY = (
    "Уточните банки и критерий через структурированные поля, "
    "без ФИО, реквизитов и зарплат отдельных сотрудников."
)


def _minimize_domain_question(request: QuestionRequest) -> MinimizedQuestion:
    text = request.question.strip().lower().rstrip("? .")
    patch: dict[str, object] = {}
    count = re.search(r"\b(?:у нас )?([1-9][0-9]{0,5}) сотрудников\b", text)
    payroll = re.search(
        r"\b(?:зарплатный )?фонд ([0-9]{1,12}(?:[.,][0-9]{1,2})?)"
        r"(?: (млн|тыс))? (?:рублей|рубля|руб|₽)\b",
        text,
    )
    if count:
        patch["employee_count"] = int(count[1])
        text = text[: count.start()] + " " + text[count.end() :]
    if payroll:
        # Positions may have shifted after removing employee count.
        payroll = re.search(payroll.re, text)
        assert payroll is not None
        multiplier = {None: Decimal(1), "млн": Decimal(1000000), "тыс": Decimal(1000)}
        patch["payroll_total"] = str(Decimal(payroll[1].replace(",", ".")) * multiplier[payroll[2]])
        text = text[: payroll.start()] + " " + text[payroll.end() :]
    if "краснодарский край" in text:
        patch["region"] = "RU-KDA"
    if "в месяц" in text or "месячный" in text:
        patch["period"] = "month"
    # Reject control characters, URLs, identifiers and all unaccounted tokens.
    if re.search(r"[^а-яёa-z ,?.\-]", text):
        return MinimizedQuestion(None, _CLARIFY)
    words = set(re.findall(r"[а-яёa-z]+(?:-[а-яёa-z]+)?", text))
    if not words or not words <= _WORDS:
        return MinimizedQuestion(None, _CLARIFY)
    banks = list(
        dict.fromkeys(
            code
            for name, code in _BANKS.items()
            if re.search(rf"(?<![а-яё]){re.escape(name)}(?![а-яё])", text)
        )
    )
    if words & {"документ", "документы", "подтверждающий", "подтверждает"}:
        intent = "documents"
    elif words & {"сравни", "сравнить", "сравнение", "выгоднее"}:
        intent = "compare"
    elif words & {"стоит", "стоимость", "тариф", "тарифы", "комиссия"} and banks:
        intent = "facts"
    else:
        intent = "clarify"
    metric = "account_monthly_fee" if words & {"счета", "счёта"} else "payroll_credit_fee"
    return MinimizedQuestion(
        json.dumps(
            {
                "intent_hint": intent,
                "bank_codes": banks,
                "metric_codes": [metric] if intent != "clarify" else [],
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
        scenario_patch=patch,
    )
