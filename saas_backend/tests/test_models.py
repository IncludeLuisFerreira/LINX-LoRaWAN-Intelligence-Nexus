from sqlalchemy.dialects.postgresql import UUID as PGUUID

from linx.models import Application, Base, Tenant, TenantUser, User


def test_all_tables_registered():
    assert set(Base.metadata.tables) == {
        "tenant",
        "application",
        "user",
        "tenant_user",
    }


def test_models_have_uuid_pk():
    for model in (Tenant, Application, User):
        pk = list(model.__table__.primary_key.columns)[0]
        assert pk.name == "id"
        assert isinstance(pk.type, PGUUID)


def test_tenant_user_has_composite_pk():
    pk_names = {c.name for c in TenantUser.__table__.primary_key.columns}
    assert pk_names == {"tenant_id", "user_id"}


def test_application_tenant_foreign_key():
    fk = list(Application.__table__.foreign_keys)[0]
    assert fk.target_fullname == "tenant.id"


def test_tenant_application_relationship():
    assert Tenant.applications.property.mapper.class_ is Application
    assert Application.tenant.property.mapper.class_ is Tenant
