import secrets

from argon2 import PasswordHasher
from fastapi import Header, HTTPException, status
from linx_shared.core.config import settings

SERVICE_TOKEN_HEADER = "X-Service-Token"
MIN_SERVICE_TOKEN_LENGTH = 32
PLACEHOLDER_SERVICE_TOKENS = frozenset(
    {"changeme", "change-me", "change-me-in-production"}
)

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Gera o hash argon2id de uma senha em texto puro."""
    return password_hasher.hash(password)


def validate_service_token(token: str) -> None:
    """Rejeita tokens fracos ou placeholders conhecidos.

    Falha com RuntimeError para ser chamado no startup da aplicação.
    """
    if not token.strip():
        raise RuntimeError("SERVICE_TOKEN must not be blank.")
    if token in PLACEHOLDER_SERVICE_TOKENS:
        raise RuntimeError(
            "SERVICE_TOKEN uses a known placeholder value; "
            "set a unique random secret."
        )
    if len(token) < MIN_SERVICE_TOKEN_LENGTH:
        raise RuntimeError(
            f"SERVICE_TOKEN must be at least "
            f"{MIN_SERVICE_TOKEN_LENGTH} characters long."
        )


def ensure_service_token_configured() -> None:
    """Valida a configuração do token no startup da aplicação."""
    token = settings.service_token or ""
    if not token:
        raise RuntimeError("SERVICE_TOKEN is not configured.")
    validate_service_token(token)


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
        )
