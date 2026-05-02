"""Database engine + session factory.

Import `engine` for low-level access (rare).
Import `SessionLocal` and use `with SessionLocal() as session:` for queries.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from applytrak.config import settings


def _sqlalchemy_url(db_url: str) -> str:
    """SQLAlchemy needs the dialect+driver prefix to use psycopg3 instead of psycopg2."""
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return db_url


engine = create_engine(
    _sqlalchemy_url(settings.database_url),
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager that commits on success, rolls back on exception, always closes."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
