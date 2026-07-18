# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.sections import (
    ApiPrefix,
    AppConfig,
    BlockchainConfig,
    PostgresConfig,
    RedisConfig,
    JwtConfig,
    SiweConfig
)


class Settings(BaseSettings):
    """App global config."""
    api: ApiPrefix = ApiPrefix()
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    app: AppConfig = AppConfig()
    blockchain: BlockchainConfig = BlockchainConfig()
    postgres: PostgresConfig = PostgresConfig()
    redis: RedisConfig = RedisConfig()
    jwt: JwtConfig = JwtConfig()
    siwe: SiweConfig = SiweConfig()
    check_interval_seconds: int = 3600

    @property
    def sync_database_url(self) -> str:
        return self.postgres.url.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()