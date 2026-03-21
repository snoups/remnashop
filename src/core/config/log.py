from src.core.enums import LogLevel

from .base import BaseConfig


class LogConfig(BaseConfig, env_prefix="LOG_"):
    to_file: bool = True
    level: LogLevel = LogLevel.DEBUG
    rotation: str = "100MB"  # "00:00"
    compression: str = "zip"
    retention: str = "3 days"
