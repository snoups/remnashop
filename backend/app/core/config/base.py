from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import REPO_ROOT


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
    )
