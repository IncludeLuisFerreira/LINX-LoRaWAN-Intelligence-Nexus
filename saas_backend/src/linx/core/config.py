from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://linx:linx@localhost:5432/linx"
    db_connect_timeout: int = 2
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
