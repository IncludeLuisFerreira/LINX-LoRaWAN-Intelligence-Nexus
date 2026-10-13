from linx_shared.core.rabbitmq import (
    build_tenant_rabbit_url,
    derive_tenant_password,
    tenant_namespace_regex,
    tenant_user,
)


def test_tenant_user_prefixes_app_id():
    assert tenant_user("abc123") == "tenant.abc123"


def test_tenant_namespace_regex_matches_only_app_namespace():
    regex = tenant_namespace_regex("abc123")
    assert regex == r"^linx\.telemetry\.abc123(\.|$)"


def test_tenant_namespace_regex_escapes_special_characters():
    regex = tenant_namespace_regex("a.b+c")
    assert r"a\.b\+c" in regex


def test_derive_tenant_password_is_deterministic():
    first = derive_tenant_password("app-1", "secret")
    second = derive_tenant_password("app-1", "secret")
    assert first == second


def test_derive_tenant_password_differs_per_app_and_secret():
    assert derive_tenant_password("app-1", "secret") != derive_tenant_password(
        "app-2", "secret"
    )
    assert derive_tenant_password("app-1", "secret") != derive_tenant_password(
        "app-1", "other"
    )


def test_derive_tenant_password_is_url_safe_and_bounded():
    password = derive_tenant_password("app-1", "secret")
    assert len(password) <= 40
    assert all(char.isalnum() or char in "-_" for char in password)


def test_build_tenant_rabbit_url_uses_tenant_credentials_and_vhost():
    url = build_tenant_rabbit_url(
        "app-1", "secret", host="rabbitmq:5672", vhost="/"
    )
    password = derive_tenant_password("app-1", "secret")
    assert url == f"amqp://tenant.app-1:{password}@rabbitmq:5672/%2F"


def test_build_tenant_rabbit_url_supports_custom_vhost():
    url = build_tenant_rabbit_url(
        "app-1", "secret", host="rabbitmq:5672", vhost="linx"
    )
    assert url.endswith("@rabbitmq:5672/linx")
