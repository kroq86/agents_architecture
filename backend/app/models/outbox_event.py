from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class OutboxEvent(Base, UUIDMixin, TimestampMixin):
    """Transactional outbox row: written in the same transaction as run + messages."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False, default="run")
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    error_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        insert_default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    signal_type: Mapped[str] = mapped_column(String(20), nullable=False, default="runtime")

    run = relationship("Run", back_populates="outbox_events")
