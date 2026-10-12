"""add nickname to devices

Revision ID: a1b2c3d4e5f6
Revises: 4d78141706c0
Create Date: 2026-10-12 19:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4d78141706c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "devices",
        sa.Column("nickname", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("devices", "nickname")
