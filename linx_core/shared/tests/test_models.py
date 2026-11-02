import re
import subprocess
import sys

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.schema import CreateIndex

from linx_shared.models import (
    Application,
    ApplicationInstance,
    Base,
    Device,
    Job,
    JobOutbox,
    Tenant,
    TenantUser,
    User,
)


def test_all_tables_registered():
    assert set(Base.metadata.tables) == {
        "application",
        "application_instances",
        "devices",
        "job_outbox",
        "jobs",
        "tenant",
        "tenant_user",
        "user",
    }


def test_device_routes_table_is_not_registered():
    assert "device_routes" not in Base.metadata.tables


def test_models_have_uuid_pk():
    for model in (Tenant, Application, ApplicationInstance, User, Device, Job):
        pk = list(model.__table__.primary_key.columns)[0]
        assert pk.name == "id"
        assert isinstance(pk.type, PGUUID)


def test_job_deduplication_key_partial_unique_index():
    indexes = {index.name: index for index in Job.__table__.indexes}
    index = indexes["uq_jobs_active_dedup"]
    assert index.unique is True
    assert [column.name for column in index.columns] == ["deduplication_key"]
    where = index.dialect_options["postgresql"]["where"]
    assert "status IN ('pending','running')" in str(where)


def test_job_tenant_created_index_is_descending():
    indexes = {index.name: index for index in Job.__table__.indexes}
    index = indexes["ix_jobs_tenant_created"]
    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "tenant_id" in ddl
    assert "created_at DESC" in ddl


def test_job_outbox_job_foreign_key():
    fk = list(JobOutbox.__table__.foreign_keys)[0]
    assert fk.target_fullname == "jobs.id"
    assert fk.ondelete == "CASCADE"


def test_tenant_user_has_composite_pk():
    pk_names = {c.name for c in TenantUser.__table__.primary_key.columns}
    assert pk_names == {"tenant_id", "user_id"}


def test_application_tenant_foreign_key():
    fk = list(Application.__table__.foreign_keys)[0]
    assert fk.target_fullname == "tenant.id"


def test_device_dev_eui_is_unique_and_indexed():
    column = Device.__table__.c.dev_eui
    assert column.unique is True
    assert column.index is True


def test_device_application_foreign_key():
    fk = list(Device.__table__.foreign_keys)[0]
    assert fk.target_fullname == "application.id"
    assert fk.ondelete == "CASCADE"


def test_tenant_application_relationship():
    assert Tenant.applications.property.mapper.class_ is Application
    assert Application.tenant.property.mapper.class_ is Tenant


def test_tenant_user_relationships():
    assert TenantUser.tenant.property.mapper.class_ is Tenant
    assert TenantUser.user.property.mapper.class_ is User
    assert Tenant.tenant_users.property.mapper.class_ is TenantUser
    assert User.tenant_users.property.mapper.class_ is TenantUser


def test_db_base_reexports_base_and_session():
    from linx_shared.db.base import Base as DBBase
    from linx_shared.db.base import SessionLocal, engine

    assert DBBase is Base
    assert engine is not None
    assert SessionLocal is not None


def test_db_base_import_registers_models():
    code = (
        "from linx_shared.db.base import Base; "
        "print(sorted(Base.metadata.tables))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    expected = (
        "['application', 'application_instances', 'devices', 'job_outbox', "
        "'jobs', 'tenant', 'tenant_user', 'user']"
    )
    assert result.stdout.strip() == expected


def test_job_outbox_has_quarantine_columns():
    columns = JobOutbox.__table__.c
    assert columns.failed_at.nullable is True
    assert columns.last_error.nullable is True


def test_jobs_status_check_constraint_matches_enum():
    from linx_shared.jobs.constants import JobStatus

    check = next(
        (
            c
            for c in Job.__table__.constraints
            if isinstance(c, CheckConstraint) and c.name == "ck_jobs_status"
        ),
        None,
    )
    assert check is not None, "ck_jobs_status não encontrado"
    sqltext = str(check.sqltext)
    for status in JobStatus:
        assert f"'{status.value}'" in sqltext
    literals = set(re.findall(r"'([a-z_]+)'", sqltext))
    assert literals == {status.value for status in JobStatus}
