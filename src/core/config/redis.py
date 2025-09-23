from pydantic import RedisDsn, SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from .base import BaseConfig
from .validators import validate_not_change_me


class RedisConfig(BaseConfig, env_prefix="REDIS_"):
    host: str
    port: int
    name: str
    password: SecretStr

    @property
    def dsn(self) -> str:
        return RedisDsn.build(
            scheme="redis",
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=self.name,
        ).unicode_string()

    @field_validator("password")
    @classmethod
    def validate_redis_password(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field
