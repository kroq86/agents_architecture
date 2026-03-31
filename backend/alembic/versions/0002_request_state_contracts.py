"""add request contract and session state tables

Revision ID: 0002_request_state_contracts
Revises: 0001_initial
Create Date: 2026-03-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_request_state_contracts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    run_columns = {col["name"] for col in inspector.get_columns("runs")}

    if "request_id" not in run_columns:
        op.add_column("runs", sa.Column("request_id", sa.String(length=36), nullable=True))
    if "session_id" not in run_columns:
        op.add_column("runs", sa.Column("session_id", sa.String(length=36), nullable=True))
    if "trace_id" not in run_columns:
        op.add_column("runs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    if "task_type" not in run_columns:
        op.add_column("runs", sa.Column("task_type", sa.String(length=60), nullable=True))
    if "user_constraints" not in run_columns:
        op.add_column("runs", sa.Column("user_constraints", sa.JSON(), nullable=True))
    if "priority" not in run_columns:
        op.add_column("runs", sa.Column("priority", sa.String(length=20), nullable=True))
    if "deadline" not in run_columns:
        op.add_column("runs", sa.Column("deadline", sa.String(length=64), nullable=True))
    if "attachments" not in run_columns:
        op.add_column("runs", sa.Column("attachments", sa.JSON(), nullable=True))

    op.execute("UPDATE runs SET request_id = id WHERE request_id IS NULL")
    op.execute("UPDATE runs SET session_id = id WHERE session_id IS NULL")
    op.execute("UPDATE runs SET trace_id = id WHERE trace_id IS NULL")
    op.execute("UPDATE runs SET task_type = 'chat' WHERE task_type IS NULL")
    op.execute("UPDATE runs SET user_constraints = '{}' WHERE user_constraints IS NULL")
    op.execute("UPDATE runs SET priority = 'normal' WHERE priority IS NULL")
    op.execute("UPDATE runs SET attachments = '[]' WHERE attachments IS NULL")

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("runs")}
    if op.f("ix_runs_request_id") not in existing_indexes:
        op.create_index(op.f("ix_runs_request_id"), "runs", ["request_id"], unique=False)
    if op.f("ix_runs_session_id") not in existing_indexes:
        op.create_index(op.f("ix_runs_session_id"), "runs", ["session_id"], unique=False)
    if op.f("ix_runs_trace_id") not in existing_indexes:
        op.create_index(op.f("ix_runs_trace_id"), "runs", ["trace_id"], unique=False)

    existing_tables = set(inspector.get_table_names())
    if "session_states" not in existing_tables:
        op.create_table(
            "session_states",
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("current_phase", sa.String(length=60), nullable=False),
            sa.Column("completed_steps", sa.JSON(), nullable=False),
            sa.Column("pending_steps", sa.JSON(), nullable=False),
            sa.Column("artifacts", sa.JSON(), nullable=False),
            sa.Column("known_blockers", sa.JSON(), nullable=False),
            sa.Column("next_action", sa.Text(), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_session_states")),
        )
        op.create_index(op.f("ix_session_states_session_id"), "session_states", ["session_id"], unique=True)

    if "facts_blocks" not in existing_tables:
        op.create_table(
            "facts_blocks",
            sa.Column("session_state_id", sa.String(length=36), nullable=False),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("value", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["session_state_id"], ["session_states.id"], name=op.f("fk_facts_blocks_session_state_id_session_states")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_facts_blocks")),
        )
        op.create_index(op.f("ix_facts_blocks_key"), "facts_blocks", ["key"], unique=False)
        op.create_index(op.f("ix_facts_blocks_session_state_id"), "facts_blocks", ["session_state_id"], unique=False)

    if "scratchpads" not in existing_tables:
        op.create_table(
            "scratchpads",
            sa.Column("session_state_id", sa.String(length=36), nullable=False),
            sa.Column("kind", sa.String(length=60), nullable=False),
            sa.Column("content", sa.JSON(), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["session_state_id"], ["session_states.id"], name=op.f("fk_scratchpads_session_state_id_session_states")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_scratchpads")),
        )
        op.create_index(op.f("ix_scratchpads_kind"), "scratchpads", ["kind"], unique=False)
        op.create_index(op.f("ix_scratchpads_session_state_id"), "scratchpads", ["session_state_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scratchpads_session_state_id"), table_name="scratchpads")
    op.drop_index(op.f("ix_scratchpads_kind"), table_name="scratchpads")
    op.drop_table("scratchpads")
    op.drop_index(op.f("ix_facts_blocks_session_state_id"), table_name="facts_blocks")
    op.drop_index(op.f("ix_facts_blocks_key"), table_name="facts_blocks")
    op.drop_table("facts_blocks")
    op.drop_index(op.f("ix_session_states_session_id"), table_name="session_states")
    op.drop_table("session_states")
    op.drop_index(op.f("ix_runs_trace_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_session_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_request_id"), table_name="runs")
    op.drop_column("runs", "attachments")
    op.drop_column("runs", "deadline")
    op.drop_column("runs", "priority")
    op.drop_column("runs", "user_constraints")
    op.drop_column("runs", "task_type")
    op.drop_column("runs", "trace_id")
    op.drop_column("runs", "session_id")
    op.drop_column("runs", "request_id")

