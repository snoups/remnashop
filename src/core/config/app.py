import re
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from src.core.constants import API_V1, ASSETS_DIR, DOMAIN_REGEX, PAYMENTS_WEBHOOK_PATH
from src.core.enums import Locale, PaymentGatewayType
from src.core.utils.types import LocaleList, StringList

from .base import BaseConfig
from .bot import BotConfig
from .build import BuildConfig
from .database import DatabaseConfig
from .redis import RedisConfig
from .remnawave import RemnawaveConfig
from .validators import validate_not_change_me


class AppConfig(BaseConfig, env_prefix="APP_"):
    domain: SecretStr
    host: str = "0.0.0.0"
    port: int = 5000

    locales: LocaleList = LocaleList([Locale.EN])
    default_locale: Locale = Locale.EN

    crypt_key: SecretStr
    assets_dir: Path = ASSETS_DIR
    origins: StringList = StringList("")

    bot: BotConfig = Field(default_factory=BotConfig)
    remnawave: RemnawaveConfig = Field(default_factory=RemnawaveConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    build: BuildConfig = Field(default_factory=BuildConfig)

    @property
    def banners_dir(self) -> Path:
        return self.assets_dir / "banners"

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

        if not re.match(DOMAIN_REGEX, field.get_secret_value()):
            raise ValueError("APP_DOMAIN has invalid format")

        return field

    @field_validator("crypt_key")
    @classmethod
    def validate_crypt_key(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)

        if not re.match(r"^[A-Za-z0-9+/=]{44}$", field.get_secret_value()):
            raise ValueError("APP_CRYPT_KEY must be a valid 44-character Base64 string")

        return field
