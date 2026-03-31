"""add quality, provenance, coverage and review tables

Revision ID: 0003_quality_and_review
Revises: 0002_request_state_contracts
Create Date: 2026-03-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_quality_and_review"
down_revision: str | None = "0002_request_state_contracts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "findings" not in existing_tables:
        op.create_table(
            "findings",
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("claim", sa.Text(), nullable=False),
            sa.Column("supporting_evidence", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("coverage_scope", sa.String(length=120), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_findings_run_id_runs")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
        )
        op.create_index(op.f("ix_findings_run_id"), "findings", ["run_id"], unique=False)

    if "provenances" not in existing_tables:
        op.create_table(
            "provenances",
            sa.Column("finding_id", sa.String(length=36), nullable=False),
            sa.Column("claim", sa.Text(), nullable=False),
            sa.Column("source_id", sa.String(length=120), nullable=True),
            sa.Column("source_name", sa.String(length=255), nullable=False),
            sa.Column("source_locator", sa.String(length=255), nullable=True),
            sa.Column("relevant_excerpt", sa.Text(), nullable=True),
            sa.Column("publication_or_effective_date", sa.String(length=80), nullable=True),
            sa.Column("retrieval_timestamp", sa.String(length=80), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], name=op.f("fk_provenances_finding_id_findings")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_provenances")),
        )
        op.create_index(op.f("ix_provenances_finding_id"), "provenances", ["finding_id"], unique=False)

    if "coverage_gaps" not in existing_tables:
        op.create_table(
            "coverage_gaps",
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("gap_type", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(length=40), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_coverage_gaps_run_id_runs")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_coverage_gaps")),
        )
        op.create_index(op.f("ix_coverage_gaps_run_id"), "coverage_gaps", ["run_id"], unique=False)

    if "human_review_items" not in existing_tables:
        op.create_table(
            "human_review_items",
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("trigger_class", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("case_summary", sa.Text(), nullable=False),
            sa.Column("uncertainty", sa.Text(), nullable=True),
            sa.Column("attempted_actions", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_human_review_items_run_id_runs")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_human_review_items")),
        )
        op.create_index(op.f("ix_human_review_items_run_id"), "human_review_items", ["run_id"], unique=False)
        op.create_index(op.f("ix_human_review_items_trigger_class"), "human_review_items", ["trigger_class"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_human_review_items_trigger_class"), table_name="human_review_items")
    op.drop_index(op.f("ix_human_review_items_run_id"), table_name="human_review_items")
    op.drop_table("human_review_items")
    op.drop_index(op.f("ix_coverage_gaps_run_id"), table_name="coverage_gaps")
    op.drop_table("coverage_gaps")
    op.drop_index(op.f("ix_provenances_finding_id"), table_name="provenances")
    op.drop_table("provenances")
    op.drop_index(op.f("ix_findings_run_id"), table_name="findings")
    op.drop_table("findings")

