"""SQLAlchemy base and transaction-scoped session helper."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Commit only on successful exit; roll back on exceptions."""
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def dispose_engine(engine: Engine) -> None:
    engine.dispose()
