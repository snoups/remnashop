from typing import Optional

from pydantic import RedisDsn, SecretStr

from app.core.config.base import BaseConfig


class RedisConfig(BaseConfig, env_prefix="REDIS_"):
    host: str = "remnashop-redis"
    port: int = 6379
    name: str = "0"
    password: Optional[SecretStr] = None

    @property
    def dsn(self) -> str:
        return RedisDsn.build(
            scheme="redis",
            password=self.password.get_secret_value() if self.password else None,
            host=self.host,
            port=self.port,
            path=self.name,
        ).unicode_string()
