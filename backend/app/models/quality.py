from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Finding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "findings"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    coverage_scope: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    run = relationship("Run", back_populates="findings")
    provenances = relationship("Provenance", back_populates="finding", cascade="all, delete-orphan")


class Provenance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "provenances"

    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True, nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relevant_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_or_effective_date: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retrieval_timestamp: Mapped[str | None] = mapped_column(String(80), nullable=True)

    finding = relationship("Finding", back_populates="provenances")


class CoverageGap(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "coverage_gaps"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    gap_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    run = relationship("Run", back_populates="coverage_gaps")


class HumanReviewItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "human_review_items"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    trigger_class: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    case_summary: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolver: Mapped[str | None] = mapped_column(String(255), nullable=True)

    run = relationship("Run", back_populates="review_items")

