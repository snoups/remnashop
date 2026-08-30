import dataclasses
from typing import Any

from app.core.events import BaseEvent
from app.modules.users import UserDto

_SAFE_USER_FIELDS = ("id", "login", "name", "role")
_SKIPPED_FIELDS = {"event_id", "occurred_at", "ip_address"}


def _sanitize_user(user: UserDto) -> dict[str, Any]:
    return {
        field: str(getattr(user, field)) if field == "role" else getattr(user, field)
        for field in _SAFE_USER_FIELDS
    }


def build_payload(event: BaseEvent) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for f in dataclasses.fields(event):
        if f.name in _SKIPPED_FIELDS:
            continue
        value = getattr(event, f.name)
        payload[f.name] = _sanitize_user(value) if isinstance(value, UserDto) else value
    return payload
