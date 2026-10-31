import uuid

import pytest
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError

from linx_shared.models import (
    Application,
    ApplicationInstance,
    Base,
    Tenant,
)
from linx_shared.models.application_instance import (
    APPLICATION_INSTANCE_STATUSES,
)


def _table():
    table = Base.metadata.tables.get("application_instances")
    assert (
        table is not None
    ), "application_instances não registrada no metadata"
    return table


def _constraints_by_name(table):
    return {constraint.name: constraint for constraint in table.constraints}


def test_application_instances_table_registered():
    assert ApplicationInstance.__tablename__ == "application_instances"
    assert _table() is ApplicationInstance.__table__


def test_application_instances_columns():
    columns = _table().c
    assert set(columns.keys()) == {
        "id",
        "app_id",
        "container_id",
        "host",
        "port",
        "status",
        "provisioned_at",
    }
    assert isinstance(columns.id.type, PGUUID)
    assert isinstance(columns.app_id.type, PGUUID)
    assert isinstance(columns.container_id.type, String)
    assert isinstance(columns.host.type, String)
    assert isinstance(columns.port.type, Integer)
    assert isinstance(columns.status.type, String)
    assert isinstance(columns.provisioned_at.type, DateTime)
    assert columns.container_id.type.length == 64
    assert columns.host.type.length == 255
    assert columns.status.type.length == 20
    assert columns.provisioned_at.type.timezone is True


def test_application_instances_id_is_uuid_primary_key():
    column = _table().c.id
    assert column.primary_key is True
    assert column.default.arg is not None
    assert column.default.arg.__name__ == uuid.uuid4.__name__


def test_application_instances_app_id_foreign_key_cascades():
    foreign_key = next(iter(_table().c.app_id.foreign_keys))
    assert foreign_key.target_fullname == "application.id"
    assert foreign_key.ondelete == "CASCADE"
    assert _table().c.app_id.nullable is False


def test_application_instances_app_id_is_unique():
    unique = _constraints_by_name(_table())["uq_application_instances_app_id"]
    assert isinstance(unique, UniqueConstraint)
    assert [column.name for column in unique.columns] == ["app_id"]


def test_application_instances_status_defaults_to_pending():
    column = _table().c.status
    assert column.nullable is False
    assert column.default.arg == "PENDING"


def test_application_instances_status_has_server_default():
    column = _table().c.status
    assert column.server_default is not None
    assert str(column.server_default.arg) == "PENDING"


def test_application_instances_status_check_constraint():
    check = _constraints_by_name(_table())["ck_application_instances_status"]
    assert isinstance(check, CheckConstraint)
    sqltext = str(check.sqltext)
    for status in APPLICATION_INSTANCE_STATUSES:
        assert f"'{status}'" in sqltext


def test_application_instances_optional_columns_are_nullable():
    columns = _table().c
    assert columns.container_id.nullable is True
    assert columns.host.nullable is True
    assert columns.port.nullable is True
    assert columns.provisioned_at.nullable is True


def test_application_instances_provisioned_at_is_timezone_aware():
    column = _table().c.provisioned_at
    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True


def _application(db_session) -> Application:
    tenant = Tenant(name="Tenant", description="", tags={})
    db_session.add(tenant)
    db_session.flush()

    application = Application(
        tenant_id=tenant.id,
        name="Application",
        description="",
        tags={},
    )
    db_session.add(application)
    db_session.flush()
    return application


def test_application_instances_status_default_is_applied_on_insert(db_session):
    application = _application(db_session)

    instance = ApplicationInstance(app_id=application.id)
    db_session.add(instance)
    db_session.flush()

    assert instance.status == "PENDING"
    assert instance.provisioned_at is None


def test_application_instances_rejects_duplicate_app_id(db_session):
    application = _application(db_session)
    db_session.add(ApplicationInstance(app_id=application.id))
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(ApplicationInstance(app_id=application.id))
            db_session.flush()


def test_application_instances_rejects_invalid_status(db_session):
    application = _application(db_session)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                ApplicationInstance(app_id=application.id, status="UNKNOWN")
            )
            db_session.flush()
