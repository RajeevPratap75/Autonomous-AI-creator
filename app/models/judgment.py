import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.agent import utcnow


class Judgment(Base):
    """An immutable record of the editorial decision made for one discovered topic."""

    __tablename__ = "judgments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id"), nullable=False, unique=True, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    agent: Mapped["Agent"] = relationship(back_populates="judgments")
    topic: Mapped["Topic"] = relationship(back_populates="judgments")


from app.models.agent import Agent  # noqa: E402
from app.models.topic import Topic  # noqa: E402
