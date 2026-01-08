from typing import Self

from pydantic import Field, SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from .base import BaseConfig
from .validators import validate_not_change_me


class WebsiteConfig(BaseConfig, env_prefix="WEBSITE_"):
    api_key: SecretStr = Field(default=SecretStr(""))
    jwt_secret: SecretStr = Field(default=SecretStr(""))
    jwt_expires_hours: int = 24
    allowed_origins: str = ""

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        if field.get_secret_value():
            validate_not_change_me(field, info)
        return field

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        if field.get_secret_value():
            validate_not_change_me(field, info)
        return field

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key.get_secret_value() and self.jwt_secret.get_secret_value())

    @property
    def origins_list(self) -> list[str]:
        if not self.allowed_origins:
            return []
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
