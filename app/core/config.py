import re
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Optional, Self

from pydantic import Field, Secret, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import API_V1, WEBHOOK_PATH
from app.core.enums import ArchiveFormat, Locale, LogLevel

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS_DIR = BASE_DIR / "app" / "assets"
DEFAULT_BANNERS_DIR = DEFAULT_ASSETS_DIR / "banners"
DEFAULT_LOCALES_DIR = DEFAULT_ASSETS_DIR / "locales"
DEFAULT_I18N_LOCALES = [Locale.EN, Locale.RU]
DEFAULT_I18N_LOCALE = Locale.EN

DEFAULT_BOT_HOST = "127.0.0.1"
DEFAULT_BOT_PORT = 5000
DEFAULT_BOT_WEBHOOK_PORT = 443
DEFAULT_BOT_RESET_WEBHOOK = True
DEFAULT_BOT_DROP_PENDING_UPDATES = False
DEFAULT_BOT_SETUP_COMMANDS = True
DEFAULT_BOT_USE_BANNERS = True

DEFAULT_DB_HOST = "remnashop-db"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_NAME = "remnashop"
DEFAULT_DB_USER = "remnashop"

DEFAULT_REDIS_HOST = "remnashop-redis"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_NAME = "0"

DEFAULT_LOG_LEVEL = LogLevel.DEBUG
DEFAULT_LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DEFAULT_LOG_ARCHIVE_FORMAT = ArchiveFormat.ZIP


class BotConfig(BaseSettings, env_prefix="BOT_"):
    token: SecretStr
    secret_token: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_hex()))
    dev_id: int
    domain: Secret[str]
    host: str = DEFAULT_BOT_HOST
    port: int = DEFAULT_BOT_PORT
    webhook_port: int = DEFAULT_BOT_WEBHOOK_PORT
    reset_webhook: bool = DEFAULT_BOT_RESET_WEBHOOK
    drop_pending_updates: bool = DEFAULT_BOT_DROP_PENDING_UPDATES
    setup_commands: bool = DEFAULT_BOT_SETUP_COMMANDS
    use_banners: bool = DEFAULT_BOT_USE_BANNERS

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, field: Secret[str]) -> Secret[str]:
        DOMAIN_REGEX = r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
        domain = field.get_secret_value()
        if not domain:
            raise ValueError("Domain cannot be empty")
        if not re.match(DOMAIN_REGEX, domain):
            raise ValueError("Invalid domain format")
        return field

    @property
    def webhook_path(self) -> str:
        return f"{API_V1}{WEBHOOK_PATH}"

    @property
    def webhook_url(self) -> SecretStr:
        url = f"https://{self.domain.get_secret_value()}:{self.webhook_port}{self.webhook_path}"
        return SecretStr(url)


class DatabaseConfig(BaseSettings, env_prefix="DB_"):
    host: str = DEFAULT_DB_HOST
    port: int = DEFAULT_DB_PORT
    name: str = DEFAULT_DB_NAME
    user: str = DEFAULT_DB_USER
    password: Secret[str]

    def dsn(self, scheme: str = "postgresql+asyncpg") -> str:
        return (
            f"{scheme}://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class RedisConfig(BaseSettings, env_prefix="REDIS_"):
    host: str = DEFAULT_REDIS_HOST
    port: int = DEFAULT_REDIS_PORT
    name: str = DEFAULT_REDIS_NAME
    username: Optional[str] = None
    password: Optional[SecretStr] = None

    def dsn(self, scheme: str = "redis") -> str:
        if self.username and self.password:
            return (
                f"{scheme}://{self.username}:{self.password.get_secret_value()}"
                f"@{self.host}:{self.port}/{self.name}"
            )
        return f"{scheme}://{self.host}:{self.port}/{self.name}"


class LoggingConfig(BaseSettings, env_prefix="LOG_"):
    level: LogLevel = DEFAULT_LOG_LEVEL
    format: str = DEFAULT_LOG_FORMAT
    archive_format: ArchiveFormat = DEFAULT_LOG_ARCHIVE_FORMAT


class I18nConfig(BaseSettings, env_prefix="I18N_"):
    locales_dir: Path = DEFAULT_LOCALES_DIR
    locales: list[Locale] = DEFAULT_I18N_LOCALES
    default_locale: Locale = DEFAULT_I18N_LOCALE


class SQLAlchemyConfig(BaseSettings, env_prefix="ALCHEMY_"):  # TODO
    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 25
    max_overflow: int = 25
    pool_timeout: int = 10
    pool_recycle: int = 3600


class AppConfig(BaseSettings):
    bot: BotConfig = Field(default_factory=BotConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    i18n: I18nConfig = Field(default_factory=I18nConfig)
    alchemy: SQLAlchemyConfig = Field(default_factory=SQLAlchemyConfig)

    origins: list[str] = []  # TODO:

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    @classmethod
    @lru_cache
    def get(cls) -> Self:
        return cls()
