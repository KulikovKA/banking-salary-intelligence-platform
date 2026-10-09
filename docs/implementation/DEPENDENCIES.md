# Зависимости объединённых блоков

Рёбра вычислены из зависимостей всех исходных этапов. Каждый старый ID входит ровно в один WORK. Внутри блоков сохранён топологический порядок.

```mermaid
flowchart TD
  WORK_01["WORK-01: High"]
  WORK_02["WORK-02: Medium"]
  WORK_01 --> WORK_02
  WORK_03["WORK-03: Extra High"]
  WORK_02 --> WORK_03
  WORK_04["WORK-04: High"]
  WORK_02 --> WORK_04
  WORK_03 --> WORK_04
  WORK_05["WORK-05: High"]
  WORK_01 --> WORK_05
  WORK_04 --> WORK_05
  WORK_06["WORK-06: Extra High"]
  WORK_04 --> WORK_06
  WORK_05 --> WORK_06
  WORK_07["WORK-07: Extra High"]
  WORK_04 --> WORK_07
  WORK_06 --> WORK_07
  WORK_08["WORK-08: High"]
  WORK_04 --> WORK_08
  WORK_06 --> WORK_08
  WORK_07 --> WORK_08
  WORK_09["WORK-09: High"]
  WORK_05 --> WORK_09
  WORK_08 --> WORK_09
  WORK_10["WORK-10: High"]
  WORK_06 --> WORK_10
  WORK_08 --> WORK_10
  WORK_09 --> WORK_10
  WORK_11["WORK-11: Extra High"]
  WORK_03 --> WORK_11
  WORK_08 --> WORK_11
  WORK_10 --> WORK_11
  WORK_12["WORK-12: High"]
  WORK_03 --> WORK_12
  WORK_06 --> WORK_12
  WORK_10 --> WORK_12
  WORK_11 --> WORK_12
  WORK_13["WORK-13: Medium"]
  WORK_07 --> WORK_13
  WORK_08 --> WORK_13
  WORK_11 --> WORK_13
  WORK_12 --> WORK_13
  WORK_14["WORK-14: Medium"]
  WORK_12 --> WORK_14
  WORK_15["WORK-15: Extra High"]
  WORK_11 --> WORK_15
  WORK_13 --> WORK_15
  WORK_14 --> WORK_15
  WORK_16["WORK-16: High"]
  WORK_01 --> WORK_16
  WORK_14 --> WORK_16
  WORK_17["WORK-17: High"]
  WORK_09 --> WORK_17
  WORK_11 --> WORK_17
  WORK_16 --> WORK_17
  WORK_18["WORK-18: High"]
  WORK_03 --> WORK_18
  WORK_14 --> WORK_18
  WORK_15 --> WORK_18
  WORK_16 --> WORK_18
  WORK_19["WORK-19: High"]
  WORK_13 --> WORK_19
  WORK_18 --> WORK_19
  WORK_20["WORK-20: —"]
  WORK_15 --> WORK_20
  WORK_16 --> WORK_20
  WORK_19 --> WORK_20
  WORK_21["WORK-21: Extra High"]
  WORK_20 --> WORK_21
  WORK_22["WORK-22: —"]
  WORK_21 --> WORK_22
```

G0 обязателен перед разработкой; G1 после WORK-05, G2 после WORK-09. WORK-17 дополнительно зависит от решения пользователя о provider; для реального AI его успешная evaluation обязательна перед WORK-20. С Fake этот блок можно оставить BLOCKED с явным ограничением release.

[Внутренняя детализация графа](DETAILED_DEPENDENCIES.md), [правила reasoning](REASONING_GUIDE.md).
