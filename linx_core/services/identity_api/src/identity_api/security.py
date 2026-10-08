import secrets

from fastapi import Header, HTTPException, status
from linx_shared.core.config import settings

SERVICE_TOKEN_HEADER = "X-Service-Token"


def verify_service_token(
    x_service_token: str | None = Header(
        default=None, alias=SERVICE_TOKEN_HEADER
    ),
) -> None:
    """Valida o token de serviço de ponta a ponta.

    Comparação em tempo constante para evitar timing attacks. Falha fechada:
    se o token não estiver configurado no ambiente, recusa a requisição.
    """
    expected = settings.service_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service token is not configured",
        )

    provided = x_service_token or ""
    if not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
            headers={"WWW-Authenticate": SERVICE_TOKEN_HEADER},
        )
