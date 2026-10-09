# Приёмка по gates

Все пороги ниже — предложенные release gates; изменение порога требует записанной причины и решения пользователя, а не редактирования теста под результат.

| Gate | Условие | Доказательство | Кто принимает |
|---|---|---|---|
| G0 Architecture | Пользователь согласовал scope, ADR proposals, порядок и нерешённые решения | Запись решения, версии docs | Пользователь |
| G1 Source feasibility | Для каждого из 4 банков хотя бы 1 релевантный официальный тарифный/условный документ, а не только news/manual; успешные scheduled fetch на ≥3 разных дня в пределах недели; policy review | manifests, hashes, fetch reports, applicability coverage | Пользователь по отчёту Luna |
| G2 POC | ≥12 документов (≥3/банк), ≥80 размеченных фактов, ≥60 gold queries; original linkage 100%, числовая precision ≥98%, condition recall ≥95%, retrieval Recall@10 ≥90%; 30 golden comparisons 100%; unsupported numbers=0 | QA-002 report с per-bank breakdown | Пользователь |
| G3 MVP security | Invite auth/RBAC/ownership, SSRF/injection checks, 0 Critical/High security issues, legal decisions for active flows | SEC reports, user matrix | Пользователь + ответственные |
| G4 Operations | 30-session load targets, restore RPO/RTO, no duplicate events on retry, all P0 E2E green | QA/LOAD/OPS reports | Пользователь |
| G5 Final audit | Независимый review, исправлены Critical/High, retest | REV reports, final status | Astra, затем пользователь |

G1 не проходит по одному API manual или поисковому snippet. Если публичных условий недостаточно для числового сравнения, зафиксировать это как результат POC, не выдумывать значения и не начинать полный UI. Пользователь решает сузить scope/добавить утверждённый источник/остановить проект.

G2 не требует искусственно получить известную цену по всем критериям: unknown/individual допустимы, но нужны минимум 3 реально сопоставимых критерия для каждой из 6 пар банков либо явное решение пользователя изменить продуктовый scope. Метрики качества считаются отдельно от coverage, чтобы высокая precision на двух фактах не маскировала пустой продукт.

С Fake LLM можно завершить G2 и технические проверки G3/G4. Финальный статус обязан явно говорить «LLM в mock-режиме». Production реального AI требует выбранного поставщика, LLM-003 и повторной evaluation на той модели; Fake-тесты не доказывают её качество.
