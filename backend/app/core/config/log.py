from app.core.config.base import BaseConfig
from app.core.enums import LogLevel


class LogConfig(BaseConfig, env_prefix="LOG_"):
    to_file: bool = True
    level: LogLevel = LogLevel.DEBUG
    rotation: str = "100MB"  # loguru also accepts a time value, e.g. "00:00" for daily rotation
    compression: str = "zip"
    retention: str = "3 days"
