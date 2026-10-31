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

APPLICATION_INSTANCE_STATUSES = (
    "PENDING",
    "PROVISIONING",
    "RUNNING",
    "ERROR",
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
        default="PENDING",
        server_default="PENDING",
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
            "status IN ('PENDING','PROVISIONING','RUNNING','ERROR')",
            name="ck_application_instances_status",
        ),
    )
