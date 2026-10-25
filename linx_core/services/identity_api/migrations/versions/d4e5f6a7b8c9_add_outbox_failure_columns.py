"""add outbox failure columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-24 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add outbox quarantine metadata."""
    op.add_column(
        "job_outbox",
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "job_outbox",
        sa.Column("last_error", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove outbox quarantine metadata."""
    op.drop_column("job_outbox", "last_error")
    op.drop_column("job_outbox", "failed_at")
