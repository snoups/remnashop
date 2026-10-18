from typing import Optional

from pydantic import SecretStr, field_validator

from app.core.config.base import BaseConfig
from app.core.utils.validators import is_valid_domain


class CabinetConfig(BaseConfig, env_prefix="CABINET_"):
    # unset when no web cabinet is deployed
    domain: Optional[str] = None
    proxy_secret: Optional[SecretStr] = None

    @property
    def url(self) -> str:
        return f"https://{self.domain}" if self.domain else ""

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, field: Optional[str]) -> Optional[str]:
        domain = (field or "").strip()
        if not domain:
            return None
        if not is_valid_domain(domain):
            raise ValueError("CABINET_DOMAIN has invalid format")
        return domain
