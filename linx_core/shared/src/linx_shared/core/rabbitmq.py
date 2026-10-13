"""Derivação de credenciais e nomes RabbitMQ por tenant.

O namespace de cada aplicação é `linx.telemetry.{app_id}`. A senha do
usuário RabbitMQ é determinística (HMAC-SHA256 do `app_id` com o segredo
do servidor), sem armazenamento de segredo no banco de controle.
"""

import base64
import hashlib
import hmac
import re
from urllib.parse import quote

PASSWORD_LENGTH = 40
NAMESPACE_PREFIX = "linx.telemetry"


def tenant_user(app_id: str) -> str:
    """Nome do usuário RabbitMQ do tenant."""
    return f"tenant.{app_id}"


def namespace_prefix(app_id: str) -> str:
    """Prefixo do namespace da aplicação no broker."""
    return f"{NAMESPACE_PREFIX}.{app_id}"


def tenant_namespace_regex(app_id: str) -> str:
    """Regex de permissão casando apenas o namespace da aplicação.

    Casa `linx.telemetry.{app_id}` e qualquer recurso aninhado
    (`linx.telemetry.{app_id}.dlq`), sem casar outros tenants.
    """
    escaped = re.escape(app_id)
    return rf"^{re.escape(NAMESPACE_PREFIX)}\.{escaped}(\.|$)"


def derive_tenant_password(app_id: str, secret: str) -> str:
    """Senha determinística do tenant (URL-safe, sem armazenamento)."""
    digest = hmac.new(
        secret.encode(), app_id.encode(), hashlib.sha256
    ).digest()
    encoded = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return encoded[:PASSWORD_LENGTH]


def build_tenant_rabbit_url(
    app_id: str,
    secret: str,
    host: str,
    vhost: str = "/",
) -> str:
    """URL AMQP do tenant com a credencial derivada."""
    password = derive_tenant_password(app_id, secret)
    user = tenant_user(app_id)
    encoded_vhost = quote(vhost, safe="")
    return f"amqp://{user}:{password}@{host}/{encoded_vhost}"
