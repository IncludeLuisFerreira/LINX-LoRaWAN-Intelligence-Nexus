import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from linx.db.base import Base

if TYPE_CHECKING:
    from linx.models.application import Application


class Tenant(Base):
    """Representa um tenant (organização) do ChirpStack v4."""

    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
    )

    can_have_gateways: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    max_gateway_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    max_device_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    private_gateways_up: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    private_gateways_down: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    tags: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
