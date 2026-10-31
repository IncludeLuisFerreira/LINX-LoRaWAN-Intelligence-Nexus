"""add jobs tables

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-10-24 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("command_exchange", sa.String(), nullable=False),
        sa.Column("command_routing_key", sa.String(), nullable=False),
        sa.Column("deduplication_key", sa.String(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed')",
            name="ck_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_jobs_active_dedup",
        "jobs",
        ["deduplication_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','running')"),
    )
    op.create_index(
        "ix_jobs_status_next_attempt",
        "jobs",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_tenant_created",
        "jobs",
        ["tenant_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_jobs_subject",
        "jobs",
        ["subject_id"],
        unique=False,
    )
    op.create_table(
        "job_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("routing_key", sa.String(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_outbox_pending",
        "job_outbox",
        ["published_at", "next_attempt_at"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_job_outbox_pending",
        table_name="job_outbox",
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.drop_table("job_outbox")
    op.drop_index(
        "ix_jobs_subject",
        table_name="jobs",
    )
    op.drop_index(
        "ix_jobs_tenant_created",
        table_name="jobs",
    )
    op.drop_index(
        "ix_jobs_status_next_attempt",
        table_name="jobs",
    )
    op.drop_index(
        "uq_jobs_active_dedup",
        table_name="jobs",
        postgresql_where=sa.text("status IN ('pending','running')"),
    )
    op.drop_table("jobs")
