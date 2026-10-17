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

    # Postgres enforces the statement/idle timeouts, asyncpg the command/connect
    # ones. Raise them for a higher-latency database such as a managed cloud one.
    statement_timeout_ms: int = 60_000
    idle_in_transaction_timeout_ms: int = 300_000
    # above statement_timeout: Postgres cancels first, with its own error
    command_timeout_s: int = 75
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
