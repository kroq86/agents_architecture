"""Transcript events + human review resolution fields."""

from alembic import op
import sqlalchemy as sa


revision = "0004_transcript_review"
down_revision = "0003_quality_and_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "run_transcript_events" not in insp.get_table_names():
        op.create_table(
            "run_transcript_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_run_transcript_events_run_id", "run_transcript_events", ["run_id"])
        op.create_index("ix_run_transcript_events_seq", "run_transcript_events", ["seq"])

    cols = {c["name"] for c in insp.get_columns("human_review_items")}
    if "resolved_at" not in cols:
        op.add_column("human_review_items", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    if "resolution" not in cols:
        op.add_column("human_review_items", sa.Column("resolution", sa.Text(), nullable=True))
    if "resolver" not in cols:
        op.add_column("human_review_items", sa.Column("resolver", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("human_review_items", "resolver")
    op.drop_column("human_review_items", "resolution")
    op.drop_column("human_review_items", "resolved_at")
    op.drop_table("run_transcript_events")
