from dataclasses import dataclass
from typing import ClassVar

import pytest

from app.core.enums import Locale, Role
from app.core.events import ActorTargetEvent, BaseEvent, EventCategory
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)


def test_event_without_category_raises_on_access() -> None:
    @dataclass(frozen=True, kw_only=True)
    class UncategorizedEvent(BaseEvent):
        pass

    with pytest.raises(AttributeError):
        _ = UncategorizedEvent().category


def test_event_with_category_exposes_it_on_the_class() -> None:
    @dataclass(frozen=True, kw_only=True)
    class CategorizedEvent(BaseEvent):
        category: ClassVar[EventCategory] = EventCategory.AUTH

    assert CategorizedEvent().category == EventCategory.AUTH


def test_actor_target_event_carries_both_users() -> None:
    @dataclass(frozen=True, kw_only=True)
    class SomeAdminEvent(ActorTargetEvent):
        category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT

    event = SomeAdminEvent(actor=OWNER, target=ADMIN)

    assert event.actor is OWNER
    assert event.target is ADMIN
    assert event.category == EventCategory.ADMIN_MANAGEMENT
