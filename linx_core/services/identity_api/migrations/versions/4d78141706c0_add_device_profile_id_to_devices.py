"""add device_profile_id to devices

Revision ID: 4d78141706c0
Revises: b7a1f0c2d9e4
Create Date: 2026-10-11 20:25:58.550561

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d78141706c0"
down_revision: Union[str, Sequence[str], None] = "b7a1f0c2d9e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "devices",
        sa.Column("device_profile_id", sa.UUID(), nullable=True),
    )
    op.execute(
        "UPDATE devices SET device_profile_id = gen_random_uuid() "
        "WHERE device_profile_id IS NULL"
    )
    op.alter_column("devices", "device_profile_id", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("devices", "device_profile_id")
