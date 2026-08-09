import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.agent import utcnow


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    dedupe_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="discovered")
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    agent: Mapped["Agent"] = relationship(back_populates="topics")
    judgments: Mapped[list["Judgment"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


from app.models.agent import Agent  # noqa: E402
