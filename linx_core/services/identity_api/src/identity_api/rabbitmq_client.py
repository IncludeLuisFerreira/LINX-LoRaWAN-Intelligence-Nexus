"""Client da management API do RabbitMQ para provisionar tenants."""

from typing import Any
from urllib.parse import quote

import httpx
from linx_shared.core.exceptions import ExternalServiceError


class RabbitMQClient:
    """Provisiona usuários e permissões por tenant via HTTP.

    Cada tenant recebe um usuário `tenant.{app_id}` com permissões
    `configure`/`write`/`read` restritas ao regex do seu namespace.
    """

    def __init__(
        self,
        base_url: str,
        admin_user: str,
        admin_password: str,
        vhost: str = "/",
        timeout: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._admin_user = admin_user
        self._admin_password = admin_password
        self._vhost = vhost
        self._timeout = timeout
        self._client = client

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        url = f"{self._base_url}{path}"
        auth = (self._admin_user, self._admin_password)
        operation = f"{method.lower()}_{path.strip('/').replace('/', '_')}"
        try:
            if self._client is not None:
                response = self._client.request(
                    method, url, json=json, auth=auth, timeout=self._timeout
                )
            else:
                response = httpx.request(
                    method, url, json=json, auth=auth, timeout=self._timeout
                )
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                service="rabbitmq",
                operation=operation,
                message=str(exc),
                original_error=exc,
            ) from exc
        if response.status_code >= 400:
            if allow_not_found and response.status_code == 404:
                return response
            raise ExternalServiceError(
                service="rabbitmq",
                operation=operation,
                message=f"HTTP {response.status_code}: {response.text}",
            )
        return response

    def put_user(self, user: str, password: str) -> None:
        self._request(
            "PUT",
            f"/api/users/{user}",
            json={"password": password, "tags": ""},
        )

    def set_permissions(self, user: str, regex: str) -> None:
        vhost = quote(self._vhost, safe="")
        self._request(
            "PUT",
            f"/api/permissions/{vhost}/{user}",
            json={"configure": regex, "write": regex, "read": regex},
        )

    def delete_user(self, user: str) -> None:
        self._request("DELETE", f"/api/users/{user}", allow_not_found=True)
