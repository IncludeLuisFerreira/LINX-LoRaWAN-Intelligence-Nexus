from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://linx:linx@localhost:5432/linx"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
