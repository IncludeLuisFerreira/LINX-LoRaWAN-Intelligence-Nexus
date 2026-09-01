import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from linx.db.base_class import Base

if TYPE_CHECKING:
    from linx.models.tenant import Tenant


class Application(Base):
    """Representa uma aplicação do ChirpStack v4, pertencente a um tenant."""

    __tablename__ = "application"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
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

    tags: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="applications")
