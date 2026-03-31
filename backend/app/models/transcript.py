from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunTranscriptEvent(Base, UUIDMixin, TimestampMixin):
    """Append-only ordered events for audit lineage (separate from user-facing messages)."""

    __tablename__ = "run_transcript_events"

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        insert_default=_utc_now,
        nullable=False,
    )

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[dict] = mapped_column("payload", JSON, default=dict, nullable=False)

    run = relationship("Run", back_populates="transcript_events")
