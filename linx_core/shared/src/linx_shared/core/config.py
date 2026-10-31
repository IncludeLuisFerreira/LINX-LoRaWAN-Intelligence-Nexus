from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Arquivo .env único na raiz de linx_core, carregado por caminho absoluto
# para funcionar independentemente do diretório de trabalho de cada serviço.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"

# Valores proibidos para segredos: não podem ser usados como credencial real.
# Um serviço que suba com qualquer um deles está operando em modo "fail open".
PLACEHOLDER_SECRETS = frozenset(
    {
        "changeme",
        "change-me",
        "change-me-in-production",
        "replace-me",
        "replace_me",
        "password",
        "secret",
        "todo",
    }
)


def require_secret(env_var: str, value: str | None) -> str:
    """Garante que um segredo foi configurado e não é um placeholder.

    Chamado por validadores de startup (field_validator). Levanta
    ``ValueError`` com mensagem acionável quando o valor está ausente ou é
    uma credencial conhecida e insegura; o serviço se recusa a subir.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(
            f"{env_var} is required and must not be empty; set it in the "
            "environment before starting the service."
        )
    if cleaned.lower() in PLACEHOLDER_SECRETS:
        raise ValueError(
            f"{env_var} uses the forbidden placeholder value {cleaned!r}; "
            "set a unique secret in the environment before starting."
        )
    return cleaned


def require_connection_string(
    env_var: str, value: str | None, forbidden_substrings: tuple[str, ...] = ()
) -> str:
    """Garante que uma connection string obrigatória é real.

    Além de rejeitar segredos placeholder vazios, rejeita substrings de
    credencial insegura (ex.: ``guest:guest`` em RabbitMQ, ``linx:linx`` em
    Postgres) para que o serviço não suba com credenciais default do broker.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(
            f"{env_var} is required and must not be empty; set it in the "
            "environment before starting the service."
        )
    lowered = cleaned.lower()
    if "changeme" in lowered or "change-me" in lowered:
        raise ValueError(
            f"{env_var} contains a placeholder credential; set a real "
            "connection string in the environment before starting."
        )
    for token in forbidden_substrings:
        if token.lower() in lowered:
            raise ValueError(
                f"{env_var} uses the insecure default credential "
                f"{token!r}; set unique credentials in the environment "
                "before starting."
            )
    return cleaned


class Settings(BaseSettings):
    # Default vazio de propósito: quem constrói a engine (identity_api,
    # agent_bridge) valida no startup e aborta. Routing herda desta classe mas
    # não usa banco, então a base não impõe o validador.
    database_url: str = ""
    db_connect_timeout: int = 2
    service_token: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


settings = Settings()
