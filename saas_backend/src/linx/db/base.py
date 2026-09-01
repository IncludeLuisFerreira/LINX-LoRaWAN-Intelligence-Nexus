from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from linx.core.config import settings
from linx.db.base_class import Base
from linx.models.application import Application  # noqa: F401
from linx.models.tenant import Tenant  # noqa: F401
from linx.models.tenant_user import TenantUser  # noqa: F401
from linx.models.user import User  # noqa: F401

engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine)

__all__ = ["Base", "engine", "SessionLocal"]
