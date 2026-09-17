from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from linx_shared.core.config import settings
from linx_shared.db.base_class import Base
from linx_shared.models.application import Application  # noqa: F401
from linx_shared.models.device_route import DeviceRoute  # noqa: F401
from linx_shared.models.tenant import Tenant  # noqa: F401
from linx_shared.models.tenant_user import TenantUser  # noqa: F401
from linx_shared.models.user import User  # noqa: F401

engine = create_engine(
    settings.database_url,
    connect_args={"connect_timeout": settings.db_connect_timeout},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)

__all__ = ["Base", "engine", "SessionLocal"]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
