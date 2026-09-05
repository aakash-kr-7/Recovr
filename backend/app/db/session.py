"""SQLAlchemy engine, session factory, and declarative Base.

SQLite is a deliberate choice for a one-week solo build, not a placeholder
— see docs/decisions/ for the reasoning if this is questioned. It is
sufficient for the write volume a demo/eval batch produces and adds zero
setup overhead for anyone cloning this repo.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
