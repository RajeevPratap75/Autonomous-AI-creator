import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), nullable=False)
    voice: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_profile: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    interests: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    opinions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cadence_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    posts: Mapped[list["Post"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    topics: Mapped[list["Topic"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    memories: Mapped[list["Memory"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    judgments: Mapped[list["Judgment"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
