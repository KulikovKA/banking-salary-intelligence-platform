import os
import sys
from logging.config import fileConfig
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.corpus import models as corpus_models  # noqa: F401
from app.db.base import Base
from app.db.migration_scope import include_object
from app.llm import models as llm_models  # noqa: F401
from app.registry import models  # noqa: F401
from app.tariffs import models as tariff_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get("DATABASE_URL", "postgresql+psycopg://bsi:bsi_local_only@127.0.0.1:5432/bsi"),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
