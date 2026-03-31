from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Run(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "runs"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(60), default="chat", nullable=False)
    user_constraints: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attachments: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="started", index=True, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="runs")
    messages = relationship("Message", back_populates="run", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="run", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="run", cascade="all, delete-orphan")
    coverage_gaps = relationship("CoverageGap", back_populates="run", cascade="all, delete-orphan")
    review_items = relationship("HumanReviewItem", back_populates="run", cascade="all, delete-orphan")
    transcript_events = relationship(
        "RunTranscriptEvent",
        back_populates="run",
        cascade="all, delete-orphan",
    )

