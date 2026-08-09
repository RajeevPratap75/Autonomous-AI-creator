from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_data_dir() -> None:
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_data_dir()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import agent, judgment, memory, post, topic  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # The project intentionally keeps SQLite zero-ops. These additive migrations let
    # an evaluator retain an existing demo database while upgrading the application.
    if not settings.database_url.startswith("sqlite"):
        return
    additions = {
        "agents": {
            "voice_profile": "TEXT NOT NULL DEFAULT '[]'",
            "interests": "TEXT NOT NULL DEFAULT '[]'",
            "opinions": "TEXT NOT NULL DEFAULT '[]'",
            "cadence_minutes": "INTEGER NOT NULL DEFAULT 180",
        },
        "topics": {
            "signal_strength": "FLOAT NOT NULL DEFAULT 0.5",
            "dedupe_hash": "VARCHAR(64) NOT NULL DEFAULT ''",
        },
        "posts": {"topic_id": "VARCHAR(36)"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
