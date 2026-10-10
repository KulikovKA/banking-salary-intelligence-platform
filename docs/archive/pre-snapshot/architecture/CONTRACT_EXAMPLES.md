# Примеры контрактов и таблица решений

Все примеры синтетические. Значения не относятся к Сберу, ВТБ, Альфа-Банку или Кубань Кредит. UUID placeholders предназначены для чтения; при реализации fixtures используют валидные UUID.

## Scenario и результат сравнения

```json
{
  "schema_version": 1,
  "bank_codes": ["synthetic_a", "synthetic_b"],
  "metric_codes": ["payroll_credit_fee"],
  "as_of": "2026-10-09",
  "scenario": {
    "region": "RU-KDA",
    "employer_segment": "sme",
    "organization_category": "commercial",
    "package_by_bank": {"synthetic_a": "standard", "synthetic_b": "base"},
    "contract_variant_by_bank": {"synthetic_a":"public_v1", "synthetic_b":"public_v2"},
    "currency": "RUB",
    "operation": "salary_credit_same_bank",
    "payer": "employer",
    "beneficiary": "employee",
    "payroll_total": "100000.00",
    "period": "per_batch",
    "as_of": "2026-10-09"
  },
  "include_stale": false
}
```

Top-level as_of и scenario.as_of после нормализации должны совпадать; при несовпадении API 422, не скрытый выбор одной даты. Клиент может не передавать scenario.as_of, тогда backend заполняет из top-level. Bank codes в production валидируются registry; synthetic codes допустимы только test dataset.

```json
{
  "comparison_id": "<uuid>",
  "corpus_revision": 12,
  "rows": [{
    "metric_code": "payroll_credit_fee",
    "cells": [
      {"bank_code":"synthetic_a", "status":"verified", "value":{"amount":"300.00","currency":"RUB"}, "fact_ids":["<fact-a>"], "evidence_ids":["<ev-a-value>","<ev-a-condition>"], "missing_inputs":[]},
      {"bank_code":"synthetic_b", "status":"verified", "value":{"amount":"500.00","currency":"RUB"}, "fact_ids":["<fact-b>"], "evidence_ids":["<ev-b-value>","<ev-b-condition>"], "missing_inputs":[]}
    ],
    "pairwise":[{"left":"synthetic_a","right":"synthetic_b","status":"better","delta":{"amount":"200.00","currency":"RUB"},"formula":"right_cost-left_cost","claim_id":"<claim-1>"}]
  }],
  "limitations":["Сравнение касается только известной комиссии за зачисление, не полной стоимости обслуживания."],
  "claims":[{
    "claim_id":"<claim-1>",
    "kind":"comparison",
    "template_code":"lower_known_component_cost",
    "supporting_fact_ids":["<fact-a>","<fact-b>"],
    "evidence_ids":["<ev-a-value>","<ev-a-condition>","<ev-b-value>","<ev-b-condition>"]
  }]
}
```

Здесь показан фрагмент ComparisonResult без обязательных scenario_echo/generated_at для краткости; это не полная schema fixture. Полные fixtures должны включать все поля DOMAIN_CONTRACTS и проверяться DTO.

## Статусы и отображение

| Ситуация | Cell | Pairwise | Пользовательская формулировка |
|---|---|---|---|
| Подтверждена комиссия 0 при выполненных условиях | verified | вычислить | «0 ₽ при …» + evidence |
| Цена не найдена | unknown | insufficient | «В проверенных источниках цена не найдена» |
| Указано «по договору» | individual | insufficient | «Условия определяются договором» |
| Подтверждено отсутствие услуги | verified boolean=false | по metric direction/neutral | «Не предусмотрено» только с evidence |
| Нужен фонд оплаты труда | unknown, missing_inputs payroll_total | insufficient | «Укажите фонд оплаты труда» |
| Регион документа неизвестен | unknown | insufficient | «Применимость в Краснодарском крае не подтверждена» |
| Источник давно не проверялся | stale | stale | «Последняя успешная проверка …» |
| Два противоречащих применимых факта | conflict | conflict | «Источники противоречат друг другу; нужна проверка» |
| Предложение относится к другому пакету | not_applicable | not_comparable | «Для выбранного сценария не применяется» |

## LLM explanation input/output

Вход включает permitted_claims с вычисленными параметрами и allowed_template_codes. Выход `{"ordered_claim_ids":["<claim-1>"],"template_by_claim":{"<claim-1>":"lower_known_component_cost"},"limitation_codes":["partial_cost"]}`. Backend проверяет, что limitation действительно относится к сравнению; модель не вправе убрать обязательное ограничение. Required limitations добавляются backend независимо от ответа модели.

Неполный output/неизвестный template → fallback. Если LLM опускает обязательный claim, backend сохраняет обязательные табличные facts и evidence; порядок не должен скрывать неблагоприятные для выбранного банка результаты. Сравнение не является рекламным ранжированием.
