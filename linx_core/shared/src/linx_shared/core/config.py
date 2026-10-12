from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Arquivo .env único na raiz de linx_core, carregado por caminho absoluto
# para funcionar independentemente do diretório de trabalho de cada serviço.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://linx:linx@localhost:5432/linx"
    db_connect_timeout: int = 2
    service_token: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


settings = Settings()
