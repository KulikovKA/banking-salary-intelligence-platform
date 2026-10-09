# Предполагаемая структура проекта

Ниже целевое дерево, а не перечень реализованных файлов. Существуют сейчас только docs и навигационный MASTER_PLAN.

```text
MASTER_PLAN.md                 # ссылка на канонический план в docs
README.md                     # будущие команды запуска
.env.example                  # без secrets
.gitignore
pyproject.toml / uv.lock
compose.yaml
backend/
  app/
    main.py
    config.py
    db/{session.py,base.py}
    common/{errors.py,ids.py,clock.py,transactions.py}
    identity/{models.py,schemas.py,service.py,permissions.py,routes.py}
    registry/{models.py,schemas.py,service.py,routes.py,policies.py}
    ingestion/{fetch.py,network_policy.py,scheduler.py,jobs.py,worker.py}
    ingestion/adapters/{base.py,sber.py,vtb.py,alfa.py,kuban.py}
    storage/{base.py,local.py,reconcile.py}
    processing/{models.py,contracts.py,html.py,pdf.py,chunks.py,versioning.py}
    facts/{models.py,schemas.py,extract.py,normalize.py,validate.py,review.py,publication.py}
    search/{service.py,schemas.py,routes.py,synonyms.py}
    comparison/{service.py,schemas.py,metrics.py,formulas.py,claims.py}
    llm/{base.py,fake.py,gateway.py,budget.py,redaction.py,providers/}
    assistant/{service.py,intent.py,tools.py,claim_validator.py,renderer.py}
    chats/{models.py,schemas.py,service.py,context.py,routes.py}
    documents/{service.py,routes.py,schemas.py}
    changes/{models.py,diff.py,outbox.py,subscriptions.py,routes.py}
    operations/{health.py,logging.py,metrics.py,audit.py,retention.py}
  alembic/versions/
  tests/{unit,integration,contracts,security}/
frontend/
  package.json / package-lock.json
  app/{login,dashboard,assistant,comparison,changes,documents,history,settings,admin,analyst}/
  components/{chat,comparison,evidence,status,forms}/
  lib/{api,auth,generated,formatting}/
  tests/{components,e2e}/
infra/
  docker/{backend.Dockerfile,frontend.Dockerfile}
  caddy/Caddyfile
  scripts/{backup,restore,migrate,bootstrap_admin}
tests/
  fixtures/{synthetic,official,manifests}/
  gold/{facts.jsonl,queries.jsonl,comparisons.jsonl}
  evaluation/{retrieval,answers,reports}/
  load/
docs/
  architecture/ADR/
  product/
  implementation/{tasks,luna_prompts}/
  quality/
  research/
  reports/                    # будущие доказательства выполнения
```

Принцип: routes → application service → domain/repository. ORM models не импортируются frontend. Network adapters не вызывают assistant. Tests fixtures отделены от production seed. Официальные большие PDF не коммитить без проверки прав/размера: manifest указывает sha256, source URL, retrieval date, controlled fixture storage. Синтетические документы явно маркированы и никогда не становятся production facts.
