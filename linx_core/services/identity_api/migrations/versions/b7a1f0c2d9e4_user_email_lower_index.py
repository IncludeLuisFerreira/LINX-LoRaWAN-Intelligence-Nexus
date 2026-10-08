"""user email case-insensitive uniqueness

Revision ID: b7a1f0c2d9e4
Revises: 43cf4d40d8cf
Create Date: 2026-10-08 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7a1f0c2d9e4"
down_revision: Union[str, Sequence[str], None] = "43cf4d40d8cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Aborta com mensagem clara se já houver emails que só diferem na caixa.
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                'SELECT lower(email) FROM "user" '
                "GROUP BY lower(email) HAVING count(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot create unique lower(email) index: existing emails "
            f"differ only by case (e.g. {duplicate[0]!r}). "
            "Resolve the duplicates before running this migration."
        )

    # Remove a unicidade case-sensitive antiga antes de normalizar os dados.
    op.drop_constraint("user_email_key", "user", type_="unique")
    op.execute('UPDATE "user" SET email = lower(email)')
    op.create_index(
        "uq_user_email_lower",
        "user",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_user_email_lower", table_name="user")
    op.create_unique_constraint("user_email_key", "user", ["email"])
