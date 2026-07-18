# app/core/sections.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


def _cfg(env_prefix: str = "") -> SettingsConfigDict:
    return SettingsConfigDict(
        env_file=['.env'],
        env_file_encoding='utf-8',
        extra="allow",
        case_sensitive=False,
        env_prefix=env_prefix,
    )


class ApiV1Prefix(BaseModel):
    prefix: str = "/api/v1"
    transfer: str = "/transfer"
    token: str = "/token"
    contract: str = "/contract"
    campaign: str = "/campaign"
    enrollment: str = "/enrollment"
    reward: str = "/reward"
    stats: str = "/stats"
    wallet: str = "/wallet"
    auth: str = "/auth"


class ApiPrefix(BaseModel):
    v1: ApiV1Prefix = ApiV1Prefix()


class AppConfig(BaseSettings):
    log_level: str
    environment: str = "dev"  # "dev" | "staging" | "production"

    model_config = _cfg("APP_")


class BlockchainConfig(BaseSettings):
    # existing
    rpc_url: str
    ws_url: str
    start_block: int = 0
 
    # new — chain + contracts
    chain_id: int
    token_address: str
    distributor_address: str
 
    # new — signer worker
    signer_private_key: str
    tx_confirmations: int = 3
    tx_tick_seconds: int = 15

    model_config = _cfg("BLOCKCHAIN_")


class PostgresConfig(BaseSettings):
    user: str
    password: str
    host: str
    port: int
    db: str

    # pool tuning
    pool_size: int = 20
    max_overflow: int = 10
    pool_pre_ping: bool = True

    @property
    def url(self) -> str:
        """Async SQLAlchemy URL built from components."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    model_config = _cfg("POSTGRES_")


class RedisConfig(BaseSettings):
    url: str
    use_ipv6: bool = False

    model_config = _cfg("REDIS_")


class JwtConfig(BaseSettings):
    """JWT signing — used by SIWE-issued session tokens."""
    secret_key: str
    algorithm: str = "HS256"

    model_config = _cfg("JWT_")


class SiweConfig(BaseSettings):
    """SIWE message validation + session cookie config."""
    domain: str = "localhost:3000"
    nonce_ttl_seconds: int = 600
    message_max_age_seconds: int = 600
    jwt_expire_hours: int = 24
    jwt_cookie_name: str = "reflow_access_token"
    cookie_secure: bool = False  # set True in prod via env var

    model_config = _cfg("SIWE_")
