"""add unique lower dev_eui index

Revision ID: 43cf4d40d8cf
Revises: 8bcf63c8173a
Create Date: 2026-10-07 00:06:00.132430

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "43cf4d40d8cf"
down_revision: Union[str, Sequence[str], None] = "8bcf63c8173a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_device_routes_dev_eui_lower",
        "device_routes",
        [sa.text("lower(dev_eui)")],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_device_routes_dev_eui_lower", table_name="device_routes")
