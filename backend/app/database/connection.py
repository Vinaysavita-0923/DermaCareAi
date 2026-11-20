"""
Database engine, session factory, and the FastAPI dependency routes
will use to get a session.

Naming note: this package is called `database/`, and the ORM table
definitions live in `database/models.py` — deliberately NOT a top-level
`app/models/` folder, because the acne classifier's checkpoint file
(Phase 6) also wants to be called "models". Keeping SQLAlchemy models
under `database/` avoids two unrelated things both being called
"models" in the same project.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite needs this flag when used with FastAPI's default threaded
# request handling; it's a no-op for other databases (e.g. PostgreSQL
# later), so it's safe to always pass it.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in the app."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session for the lifetime of
    one request, and always closes it afterwards — even if the request
    handler raises. Routes will use this as:

        def some_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
