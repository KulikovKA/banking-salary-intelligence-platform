> Детализация исходных 62 этапов. Актуальные единицы исполнения — 22 WORK-блока в [MASTER_PLAN](MASTER_PLAN.md). Исходные ID сохранены для трассировки требований. Старый порядок использовать только как справку; уровни reasoning см. в обновлённых ТЗ.

# Граф зависимостей

Граф соответствует TASK_INDEX.json; технические циклы запрещены. Это зависимости результатов, а не обещание параллельной работы агентов. По умолчанию Luna исполняет последовательно.

```mermaid
flowchart TD
  SRC_001["SRC-001"]
  SRC_001 --> INF_001
  INF_001 --> INF_002
  INF_002 --> DB_001
  DB_001 --> STO_001
  STO_001 --> NET_001
  NET_001 --> JOB_001
  NET_001 --> HTML_001
  STO_001 --> PDF_001
  DB_001 --> DB_002
  HTML_001 --> TXT_001
  PDF_001 --> TXT_001
  DB_002 --> TXT_001
  TXT_001 --> VER_001
  JOB_001 --> VER_001
  SRC_001 --> ING_001
  VER_001 --> ING_001
  SRC_001 --> ING_002
  VER_001 --> ING_002
  SRC_001 --> ING_003
  VER_001 --> ING_003
  SRC_001 --> ING_004
  VER_001 --> ING_004
  ING_001 --> QA_001
  ING_002 --> QA_001
  ING_003 --> QA_001
  ING_004 --> QA_001
  DB_002 --> DB_003
  DB_003 --> FACT_001
  FACT_001 --> FACT_002
  QA_001 --> FACT_002
  FACT_002 --> FACT_003
  FACT_003 --> FACT_004
  VER_001 --> FACT_004
  TXT_001 --> SRCH_001
  FACT_004 --> SRCH_001
  FACT_004 --> CMP_001
  CMP_001 --> CMP_002
  FACT_001 --> LLM_001
  SRCH_001 --> AI_001
  CMP_002 --> AI_001
  LLM_001 --> AI_001
  AI_001 --> AI_002
  VER_001 --> DOC_001
  AI_002 --> API_001
  DOC_001 --> API_001
  API_001 --> UI_001
  UI_001 --> QA_002
  QA_001 --> QA_002
  QA_002 --> DB_004
  DB_003 --> DB_004
  DB_004 --> AUTH_001
  AUTH_001 --> AUTH_002
  AUTH_002 --> AUTH_003
  DOC_001 --> AUTH_003
  DB_004 --> LLM_002
  LLM_001 --> LLM_002
  AUTH_003 --> LLM_002
  AUTH_003 --> CHAT_001
  DB_004 --> CHAT_001
  CHAT_001 --> CHAT_002
  AI_001 --> CHAT_002
  CHAT_002 --> AI_003
  LLM_002 --> AI_003
  AI_002 --> AI_003
  JOB_001 --> AI_003
  DB_004 --> DB_005
  FACT_004 --> DB_005
  DB_005 --> CHG_001
  FACT_004 --> CHG_001
  CHG_001 --> NTF_001
  AUTH_003 --> NTF_001
  CHG_001 --> JOB_002
  JOB_001 --> JOB_002
  AI_003 --> API_002
  NTF_001 --> API_002
  JOB_002 --> API_002
  AUTH_003 --> API_002
  API_002 --> UI_002
  UI_001 --> UI_002
  UI_002 --> UI_003
  AI_003 --> UI_003
  UI_002 --> UI_004
  CMP_002 --> UI_004
  DOC_001 --> UI_004
  UI_002 --> UI_005
  NTF_001 --> UI_005
  JOB_002 --> UI_005
  UI_002 --> UI_006
  API_002 --> UI_006
  API_002 --> OPS_001
  UI_006 --> SEC_001
  OPS_001 --> SEC_001
  SEC_001 --> SEC_002
  LLM_002 --> SEC_002
  OPS_001 --> SEC_003
  SRC_001 --> SEC_003
  LLM_002 --> LLM_003
  SEC_003 --> LLM_003
  QA_002 --> LLM_003
  SEC_003 --> OPS_002
  STO_001 --> OPS_002
  OPS_002 --> OPS_003
  OPS_001 --> OPS_003
  SEC_002 --> OPS_003
  UI_003 --> QA_003
  UI_004 --> QA_003
  UI_005 --> QA_003
  UI_006 --> QA_003
  OPS_003 --> QA_003
  QA_003 --> LOAD_001
  LOAD_001 --> REV_001
  SEC_001 --> REV_001
  SEC_002 --> REV_001
  SEC_003 --> REV_001
  REV_001 --> REV_002
  REV_002 --> REV_003
```

G0 предшествует всем задачам. G1 принимается по QA-001, G2 по QA-002; B* задачи требуют G2. G3/G4 предшествуют независимому аудиту. LLM-003 — отдельная ветвь с внешним решением пользователя; для real AI release её результат становится обязательным входом REV-001.

Потенциально независимы: HTML-001/PDF-001/DB-002, четыре adapters после VER-001, UI-003/004/005/006 после готовых API. Однако shared DTO, migrations и общий pipeline меняются последовательно. Новый migration file всегда согласует single head; нельзя параллельно генерировать конкурирующие ревизии без интеграции.

Критическая цепочка: source feasibility → archive/fetch → parsing/versioning → 4 adapters/G1 → evidence facts/publication → deterministic comparison → POC/G2 → auth/chats/events/API → E2E/security/restore/load → independent review/fixes/retest.
