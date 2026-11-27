"""lowercase application_instances status e CHECK de porta

Revision ID: b8c9d0e1f2a3
Revises: f6a7b8c9d0e1
Create Date: 2026-11-27 16:45:00.000000

Normaliza os valores de ``application_instances.status`` para minúsculas,
alinhando o banco ao modelo compartilhado (``pending``, ``provisioning``,
``running``, ``error``), atualiza o ``server_default`` e adiciona o CHECK de
faixa de porta. Portas fora de ``1..65535`` são zeradas para ``NULL`` antes da
criação do CHECK.

O downgrade restaura o CHECK/default em maiúsculas e reverte o casing dos
dados com ``upper()`` (lossless, pois o CHECK antigo só aceitava maiúsculas).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # O CHECK antigo (maiúsculas) é validado linha a linha no UPDATE, então
    # precisa ser removido antes de normalizar os dados.
    op.drop_constraint(
        "ck_application_instances_status",
        "application_instances",
        type_="check",
    )

    op.execute("UPDATE application_instances SET status = lower(status)")

    op.create_check_constraint(
        "ck_application_instances_status",
        "application_instances",
        "status IN ('pending','provisioning','running','error')",
    )

    op.alter_column(
        "application_instances",
        "status",
        server_default="pending",
    )

    # O CHECK de porta valida as linhas existentes na criação; sem esta
    # sanitização, portas inválidas (provisioner defeituoso) abortariam a
    # migração.
    op.execute(
        "UPDATE application_instances SET port = NULL "
        "WHERE port IS NOT NULL AND (port < 1 OR port > 65535)"
    )

    op.create_check_constraint(
        "ck_application_instances_port",
        "application_instances",
        "port IS NULL OR port BETWEEN 1 AND 65535",
    )


def downgrade() -> None:
    """Downgrade schema.

    Reverte o casing dos dados com ``upper()`` antes de recriar o CHECK em
    maiúsculas; como o CHECK antigo só aceitava maiúsculas, a transformação é
    lossless.
    """
    op.drop_constraint(
        "ck_application_instances_port",
        "application_instances",
        type_="check",
    )

    op.alter_column(
        "application_instances",
        "status",
        server_default="PENDING",
    )

    op.drop_constraint(
        "ck_application_instances_status",
        "application_instances",
        type_="check",
    )

    op.execute("UPDATE application_instances SET status = upper(status)")

    op.create_check_constraint(
        "ck_application_instances_status",
        "application_instances",
        "status IN ('PENDING','PROVISIONING','RUNNING','ERROR')",
    )
