"""remove device_routes table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-24 23:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove a tabela órfã device_routes e seus índices."""
    op.drop_index("uq_device_routes_dev_eui_lower", table_name="device_routes")
    op.drop_index(op.f("ix_device_routes_dev_eui"), table_name="device_routes")
    op.drop_index(op.f("ix_device_routes_app_id"), table_name="device_routes")
    op.drop_table("device_routes")


def downgrade() -> None:
    """Recria a tabela device_routes para rollback."""
    op.create_table(
        "device_routes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dev_eui", sa.String(length=16), nullable=False),
        sa.Column("app_id", sa.UUID(), nullable=False),
        sa.Column("agent_endpoint", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["app_id"], ["application.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_device_routes_dev_eui"),
        "device_routes",
        ["dev_eui"],
        unique=True,
    )
    op.create_index(
        op.f("ix_device_routes_app_id"),
        "device_routes",
        ["app_id"],
        unique=False,
    )
    op.create_index(
        "uq_device_routes_dev_eui_lower",
        "device_routes",
        [sa.text("lower(dev_eui)")],
        unique=True,
    )
