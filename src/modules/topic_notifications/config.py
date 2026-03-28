from functools import cached_property
from typing import Optional

from pydantic import model_validator

from src.core.config.base import BaseConfig


class TopicNotificationConfig(BaseConfig, env_prefix="TOPIC_NOTIFIER_"):
    enabled: bool = False
    chat_id: Optional[int] = None
    default_thread_id: Optional[int] = None
    suppress_admin_dms: bool = True
    routes: str = ""

    @classmethod
    def get(cls) -> "TopicNotificationConfig":
        return cls()

    @property
    def is_configured(self) -> bool:
        return self.enabled and self.chat_id is not None

    @cached_property
    def route_map(self) -> dict[str, int]:
        if not self.routes.strip():
            return {}

        parsed: dict[str, int] = {}
        for chunk in self.routes.split(","):
            item = chunk.strip()
            if not item:
                continue

            key, sep, value = item.partition(":")
            if sep != ":":
                raise ValueError(
                    "TOPIC_NOTIFIER_ROUTES must use 'KEY:THREAD_ID' pairs separated by commas"
                )

            normalized_key = key.strip().upper()
            if not normalized_key:
                raise ValueError("TOPIC_NOTIFIER_ROUTES contains an empty route key")

            try:
                parsed[normalized_key] = int(value.strip())
            except ValueError as exc:
                raise ValueError(
                    f"TOPIC_NOTIFIER_ROUTES contains invalid thread id for key '{normalized_key}'"
                ) from exc

        return parsed

    @model_validator(mode="after")
    def validate_enabled_settings(self) -> "TopicNotificationConfig":
        if not self.enabled:
            return self

        if self.chat_id is None:
            raise ValueError("TOPIC_NOTIFIER_CHAT_ID is required when TOPIC_NOTIFIER_ENABLED=true")

        _ = self.route_map
        return self
