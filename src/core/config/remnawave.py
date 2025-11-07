import re

from httpx import Cookies
from pydantic import SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from src.core.constants import DOMAIN_REGEX

from .base import BaseConfig
from .validators import validate_not_change_me


class RemnawaveConfig(BaseConfig, env_prefix="REMNAWAVE_"):
    host: SecretStr
    token: SecretStr
    caddy_token: SecretStr = SecretStr("")
    webhook_secret: SecretStr
    cookie: SecretStr = SecretStr("")

    @property
    def is_external(self) -> bool:
        return self.host.get_secret_value() != "remnawave"

    @property
    def url(self) -> SecretStr:
        if self.is_external:
            url = f"https://{self.host.get_secret_value()}"
            return SecretStr(url)
        else:
            url = f"http://{self.host.get_secret_value()}:3000"
            return SecretStr(url)

    @property
    def cookies(self) -> Cookies:
        cookie = self.cookie.get_secret_value()
        cookies = Cookies()

        if not self.cookie:
            return cookies

        key, value = cookie.split("=", 1)
        cookies.set(key.strip(), value.strip())

        return cookies

    @field_validator("host")
    @classmethod
    def validate_host(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        host = field.get_secret_value()

        if host == "remnawave" or re.match(DOMAIN_REGEX, host):
            validate_not_change_me(field, info)
            return field

        raise ValueError(
            "REMNAWAVE_HOST must be 'remnawave' (docker) or a valid domain (e.g., example.com)"
        )

    @field_validator("token")
    @classmethod
    def validate_remnawave_token(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field

    @field_validator("webhook_secret")
    @classmethod
    def validate_remnawave_webhook_secret(
        cls,
        field: SecretStr,
        info: FieldValidationInfo,
    ) -> SecretStr:
        validate_not_change_me(field, info)
        return field

    @field_validator("cookie")
    @classmethod
    def validate_cookie(cls, field: SecretStr) -> SecretStr:
        cookie = field.get_secret_value()

        if not cookie:
            return field

        cookie = cookie.strip()

        if "=" not in cookie or cookie.startswith("=") or cookie.endswith("="):
            raise ValueError("REMNAWAVE_COOKIE must be in 'key=value' format")

        return field
