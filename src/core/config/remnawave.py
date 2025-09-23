import re

from pydantic import SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from src.core.constants import DOMAIN_REGEX

from .base import BaseConfig
from .validators import validate_not_change_me


class RemnawaveConfig(BaseConfig, env_prefix="REMNAWAVE_"):
    # TODO: Ensure connection to the panel within a single Docker network
    host: SecretStr
    token: SecretStr

    @property
    def url(self) -> SecretStr:
        url = f"https://{self.host.get_secret_value()}"
        return SecretStr(url)

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
