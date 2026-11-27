import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from linx_shared.db.base_class import Base

# Política de casing (#247): valores de status são minúsculos em todo o
# sistema, alinhados a jobs.status ("pending", "queued", ...). Nunca use
# maiúsculas em status persistido, schema ou payload de API.
APPLICATION_INSTANCE_STATUSES = (
    "pending",
    "provisioning",
    "running",
    "error",
)


class ApplicationInstance(Base):
    """Representa o container provisionado para uma aplicação."""

    __tablename__ = "application_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application.id", ondelete="CASCADE"),
        nullable=False,
    )

    container_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    host: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    provisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "app_id",
            name="uq_application_instances_app_id",
        ),
        CheckConstraint(
            "status IN ('pending','provisioning','running','error')",
            name="ck_application_instances_status",
        ),
        CheckConstraint(
            "port IS NULL OR port BETWEEN 1 AND 65535",
            name="ck_application_instances_port",
        ),
    )
