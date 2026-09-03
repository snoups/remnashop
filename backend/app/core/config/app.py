import re
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from app.core.config.base import BaseConfig
from app.core.config.bot import BotConfig
from app.core.config.build import BuildConfig
from app.core.config.database import DatabaseConfig
from app.core.config.log import LogConfig
from app.core.config.redis import RedisConfig
from app.core.config.remnawave import RemnawaveConfig
from app.core.config.validators import validate_not_change_me
from app.core.constants import API_V1, ASSETS_DIR, MEDIA_DIR, PAYMENTS_WEBHOOK_PATH
from app.core.enums import Locale, PaymentGatewayType
from app.core.types import StringList
from app.core.utils.validators import is_valid_domain


class AppConfig(BaseConfig, env_prefix="APP_"):
    domain: SecretStr
    host: str = "0.0.0.0"
    port: int = 5000
    metrics_port: int = 9110

    default_locale: Locale = Locale.EN

    crypt_key: SecretStr
    jwt_secret: SecretStr
    assets_dir: Path = ASSETS_DIR
    media_dir: Path = MEDIA_DIR
    origins: StringList = StringList("")
    swagger_enabled: bool = False
    secure_cookies: bool = True

    bot: BotConfig = Field(default_factory=BotConfig)
    remnawave: RemnawaveConfig = Field(default_factory=RemnawaveConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    build: BuildConfig = Field(default_factory=BuildConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    @property
    def translations_dir(self) -> Path:
        return self.assets_dir / "translations"

    def get_webhook(self, gateway_type: PaymentGatewayType) -> str:
        domain = f"https://{self.domain.get_secret_value()}"
        path = f"{API_V1 + PAYMENTS_WEBHOOK_PATH}/{gateway_type.lower()}"
        return domain + path

    @classmethod
    def get(cls) -> Self:
        return cls()

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)

        if not is_valid_domain(field.get_secret_value()):
            raise ValueError("APP_DOMAIN has invalid format")

        return field

    @field_validator("crypt_key")
    @classmethod
    def validate_crypt_key(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)

        if not re.match(r"^[A-Za-z0-9+/=]{44}$", field.get_secret_value()):
            raise ValueError("APP_CRYPT_KEY must be a valid 44-character Base64 string")

        return field

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)

        if len(field.get_secret_value()) < 32:
            raise ValueError("APP_JWT_SECRET must be at least 32 characters long")

        return field
