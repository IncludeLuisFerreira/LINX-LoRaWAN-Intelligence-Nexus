import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from linx_shared.db.base_class import Base
from linx_shared.jobs.constants import JobStatus


class Job(Base):
    """Representa um job assíncrono durável."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String,
        default=JobStatus.PENDING.value,
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    error: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    command_exchange: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    command_routing_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    deduplication_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __init__(self, **kwargs: Any) -> None:
        now = datetime.now(timezone.utc)
        kwargs.setdefault("version", 1)
        kwargs.setdefault("status", JobStatus.PENDING.value)
        kwargs.setdefault("attempts", 0)
        kwargs.setdefault("max_attempts", 3)
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        super().__init__(**kwargs)

    __table_args__ = (
        Index(
            "uq_jobs_active_dedup",
            "deduplication_key",
            unique=True,
            postgresql_where=text("status IN ('pending','running')"),
        ),
        Index("ix_jobs_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_jobs_tenant_created", "tenant_id", "created_at"),
        Index("ix_jobs_subject", "subject_id"),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed')",
            name="ck_jobs_status",
        ),
    )
