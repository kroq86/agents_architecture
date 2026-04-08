"""Transactional outbox for async chat processing."""

from alembic import op
import sqlalchemy as sa


revision = "0005_outbox_events"
down_revision = "0004_transcript_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "outbox_events" not in insp.get_table_names():
        op.create_table(
            "outbox_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("event_schema_version", sa.Integer(), nullable=False),
            sa.Column("aggregate_type", sa.String(length=32), nullable=False),
            sa.Column("aggregate_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("request_id", sa.String(length=36), nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("max_attempts", sa.Integer(), nullable=False),
            sa.Column("error_class", sa.String(length=32), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lease_owner", sa.String(length=64), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("signal_type", sa.String(length=20), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
        op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
        op.create_index("ix_outbox_events_run_id", "outbox_events", ["run_id"])
        op.create_index("ix_outbox_events_request_id", "outbox_events", ["request_id"])
        op.create_index("ix_outbox_events_status", "outbox_events", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "outbox_events" in insp.get_table_names():
        op.drop_table("outbox_events")
