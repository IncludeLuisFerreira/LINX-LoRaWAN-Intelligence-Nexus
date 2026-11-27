"""Autenticação JWT de requisições ao Client Agent (issue #83).

O token é emitido pelo SaaS (`identity_api`) e validado localmente com a
chave pública RS256 configurada em `JWT_PUBLIC_KEY`.
"""

from typing import Any

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from agent.config import AgentSettings

BEARER_SCHEME = "bearer"
JWT_ALGORITHM = "RS256"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Valida `Authorization: Bearer <token>` e devolve as claims do JWT.

    Levanta `401` para header ausente, esquema diferente de Bearer, token
    vazio, assinatura inválida, algoritmo diferente de RS256 ou claims
    expiradas. A chave pública vem de `JWT_PUBLIC_KEY` (env).
    """
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != BEARER_SCHEME or not separator or not token.strip():
        raise _unauthorized()

    token = token.strip()

    public_key = AgentSettings().jwt_public_key.replace("\\n", "\n").strip()
    if not public_key:
        raise _unauthorized()

    try:
        payload = jwt.decode(token, public_key, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise _unauthorized() from exc

    return payload
