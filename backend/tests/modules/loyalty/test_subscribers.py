from typing import Any

import pytest

from app.core.enums import Locale, Role
from app.core.event_bus import EventBus
from app.modules.account_merge import AccountsMergedEvent
from app.modules.loyalty.subscribers import register_subscribers
from app.modules.loyalty.tasks import recalculate_loyalty_discounts_task
from app.modules.users import UserDto
from tests.fakes.events import stored_event


def _user(user_id: int, role: Role = Role.USER) -> UserDto:
    return UserDto(
        id=user_id, login=f"u{user_id}", name=f"u{user_id}", role=role, language=Locale.EN
    )


async def test_merge_recalculates_target_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def _kiq(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(recalculate_loyalty_discounts_task, "kiq", _kiq)
    bus = EventBus()
    register_subscribers(bus)
    event = AccountsMergedEvent(actor=_user(1, Role.ADMIN), target=_user(7), source=_user(8))

    await bus.dispatch_stored(stored_event(event))

    assert calls == [{"user_ids": [7]}]
