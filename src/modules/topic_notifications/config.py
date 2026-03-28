from functools import cached_property
from typing import Optional

from pydantic import model_validator

from src.core.config.base import BaseConfig


class TopicNotificationConfig(BaseConfig, env_prefix="TELEGRAM_TOPICS_"):
    mode: int = 0
    group_id: Optional[int] = None
    default_topic_id: Optional[int] = None
    routes: str = ""

    @classmethod
    def get(cls) -> "TopicNotificationConfig":
        return cls()

    @property
    def is_configured(self) -> bool:
        return self.mode in (1, 2) and self.group_id is not None

    @cached_property
    def route_map(self) -> dict[str, int]:
        # Один раз разбираем строку маршрутов из .env в словарь.
        # Дальше по этому словарю быстро ищется topic id для каждого события.
        if not self.routes.strip():
            return {}

        route_map: dict[str, int] = {}
        for chunk in self.routes.split(","):
            item = chunk.strip()
            if not item:
                continue

            key, sep, value = item.partition(":")
            if sep != ":":
                raise ValueError(
                    "TELEGRAM_TOPICS_ROUTES must use 'KEY:TOPIC_ID' pairs separated by commas"
                )

            normalized_key = key.strip().upper()
            if not normalized_key:
                raise ValueError("TELEGRAM_TOPICS_ROUTES contains an empty route key")

            try:
                route_map[normalized_key] = int(value.strip())
            except ValueError as exc:
                raise ValueError(
                    f"TELEGRAM_TOPICS_ROUTES contains invalid topic id for key '{normalized_key}'"
                ) from exc

        return route_map

    @model_validator(mode="after")
    def validate_enabled_settings(self) -> "TopicNotificationConfig":
        if self.mode not in (0, 1, 2):
            raise ValueError("TELEGRAM_TOPICS_MODE must be 0, 1 or 2")

        if self.mode == 0:
            return self

        if self.group_id is None:
            raise ValueError(
                "TELEGRAM_TOPICS_GROUP_ID is required when TELEGRAM_TOPICS_MODE is 1 or 2"
            )

        # Если функционал включен, валидируем маршруты уже на старте.
        # Так ошибки в конфиге ловятся сразу, а не в момент отправки уведомления.
        _ = self.route_map
        return self
