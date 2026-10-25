import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from linx_shared.db.base_class import Base


class JobOutbox(Base):
    """Mensagem pendente de publicação no broker."""

    __tablename__ = "job_outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    exchange: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    routing_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __init__(self, **kwargs: Any) -> None:
        now = datetime.now(timezone.utc)
        kwargs.setdefault("attempts", 0)
        kwargs.setdefault("next_attempt_at", now)
        kwargs.setdefault("created_at", now)
        super().__init__(**kwargs)

    __table_args__ = (
        Index(
            "ix_job_outbox_pending",
            "published_at",
            "next_attempt_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )
