"""
SQLAlchemy engine + session factory.
Connection pooling configured for horizontal scalability (stateless API workers).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs = {"pool_pre_ping": True, "pool_recycle": 1800}
if _is_sqlite:
    # SQLite: single-file DB, no real connection pool needed. check_same_thread=False
    # is required because FastAPI/uvicorn can service a single session across threads.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # MySQL/Postgres: real connection pool for concurrent workers.
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
