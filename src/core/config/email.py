from pydantic import SecretStr

from .base import BaseConfig


class EmailConfig(BaseConfig, env_prefix="EMAIL_"):
    enabled: bool = False

    host: str = ""
    port: int = 587
    use_tls: bool = True
    use_ssl: bool = False

    username: SecretStr = SecretStr("")
    password: SecretStr = SecretStr("")

    from_email: str = ""
    from_name: str = "Oldnet"

    verification_code_ttl_minutes: int = 15
