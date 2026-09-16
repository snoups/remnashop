from pydantic import PostgresDsn, SecretStr, ValidationInfo, field_validator

from app.core.config.base import BaseConfig
from app.core.config.validators import validate_not_change_me


class DatabaseConfig(BaseConfig, env_prefix="DATABASE_"):
    host: str = "remnashop-db"
    port: int = 5432
    name: str = "remnashop"
    user: str = "remnashop"
    password: SecretStr

    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800

    # All four are "give up instead of hanging forever" safety nets --
    # statement/idle timeouts are enforced by Postgres itself, command/connect
    # timeouts by the asyncpg driver. Defaults match what was previously
    # hardcoded in DatabaseProvider.get_engine(); override for a DB with
    # higher latency (e.g. a managed cloud Postgres) without editing code.
    statement_timeout_ms: int = 60_000
    idle_in_transaction_timeout_ms: int = 300_000
    command_timeout_s: int = 30
    connect_timeout_s: int = 10

    @property
    def dsn(self) -> str:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=self.name,
        ).unicode_string()

    @field_validator("password")
    @classmethod
    def validate_database_password(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field
