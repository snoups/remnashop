import re
from typing import Final, Optional

from httpx import Cookies
from pydantic import SecretStr, ValidationInfo, field_validator

from app.core.config.base import BaseConfig
from app.core.config.validators import validate_not_change_me
from app.core.constants import REMNASHOP_PREFIX
from app.core.utils.validators import is_valid_domain

# the panel caps usernames at 36: prefix + int32 id + "_" + 8 hex
_USERNAME_PREFIX: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]{1,16}$")


class RemnawaveConfig(BaseConfig, env_prefix="REMNAWAVE_"):
    host: SecretStr = SecretStr("http://remnawave:3000")
    token: SecretStr
    caddy_token: SecretStr = SecretStr("")
    cf_client_id: SecretStr = SecretStr("")
    cf_client_secret: SecretStr = SecretStr("")
    webhook_secret: Optional[SecretStr] = None
    cookie: SecretStr = SecretStr("")
    username_prefix: str = REMNASHOP_PREFIX

    @property
    def is_external(self) -> bool:
        return self.url.get_secret_value().startswith("https://")

    @property
    def url(self) -> SecretStr:
        clean_host = self.host.get_secret_value().strip().rstrip("/")

        if "://" in clean_host:
            final_url = clean_host
        elif is_valid_domain(clean_host):
            final_url = f"https://{clean_host}"
        else:
            final_url = f"http://{clean_host}"

        host_part = final_url.split("://")[-1]
        if ":" not in host_part and final_url.startswith("http://"):
            final_url = f"{final_url}:3000"

        return SecretStr(final_url)

    @property
    def cookies(self) -> Cookies:
        raw_cookie = self.cookie.get_secret_value()
        cookies = Cookies()

        if raw_cookie and "=" in raw_cookie:
            key, value = raw_cookie.split("=", 1)
            cookies.set(key.strip(), value.strip())

        return cookies

    @field_validator("token")
    @classmethod
    def validate_token(cls, field: SecretStr, info: ValidationInfo) -> SecretStr:
        validate_not_change_me(field, info)
        return field

    @field_validator("webhook_secret")
    @classmethod
    def validate_optional_secret(
        cls, field: Optional[SecretStr], info: ValidationInfo
    ) -> Optional[SecretStr]:
        if field is None:
            return field
        validate_not_change_me(field, info)
        return field

    @field_validator("username_prefix")
    @classmethod
    def validate_username_prefix(cls, field: str) -> str:
        if not _USERNAME_PREFIX.match(field):
            raise ValueError("REMNAWAVE_USERNAME_PREFIX must be 1-16 of a-z, 0-9 and _")
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
