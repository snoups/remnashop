from pydantic import PostgresDsn, SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from .base import BaseConfig
from .validators import validate_not_change_me


class DatabaseConfig(BaseConfig, env_prefix="DATABASE_"):
    host: str = "remnashop-db"
    port: int = 5432
    name: str = "remnashop"
    user: str = "remnashop"
    password: SecretStr

    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 30
    max_overflow: int = 30
    pool_timeout: int = 10
    pool_recycle: int = 3600

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
    def validate_database_password(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field
