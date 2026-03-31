from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class SessionState(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "session_states"

    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    current_phase: Mapped[str] = mapped_column(String(60), default="intake", nullable=False)
    completed_steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    pending_steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    artifacts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    known_blockers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    facts = relationship("FactsBlock", back_populates="session", cascade="all, delete-orphan")
    scratchpads = relationship("Scratchpad", back_populates="session", cascade="all, delete-orphan")


class FactsBlock(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "facts_blocks"

    session_state_id: Mapped[str] = mapped_column(
        ForeignKey("session_states.id"),
        index=True,
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    session = relationship("SessionState", back_populates="facts")


class Scratchpad(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scratchpads"

    session_state_id: Mapped[str] = mapped_column(
        ForeignKey("session_states.id"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    session = relationship("SessionState", back_populates="scratchpads")

