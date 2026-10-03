import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.modules.announcements.feed import REPO_RAW_BASE, FeedItem, parse_feed
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
LONG_AGO = NOW - timedelta(days=365)


def _items(*overrides: dict[str, Any]) -> list[FeedItem]:
    base: dict[str, Any] = {
        "title": {"en": "t"},
        "notify_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    return parse_feed(json.dumps({"items": [{**base, **o} for o in overrides]}).encode())


@pytest.fixture
async def admin(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        return await user_repository.create(CreateUserDto(login="adm", name="adm", role=Role.ADMIN))


async def test_replace_all_upserts_and_removes_missing(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(_items({"id": "a"}, {"id": "b"}))
    await announcement_repository.replace_all(_items({"id": "b", "icon": "gift"}, {"id": "c"}))

    rows = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    assert sorted(r.id for r in rows) == ["b", "c"]
    assert next(r for r in rows if r.id == "b").icon == "gift"


async def test_slide_image_becomes_an_absolute_repo_url(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(
        _items({"id": "a", "slides": [{"image": "a/1.webp", "text": {"en": "x"}}]})
    )
    [row] = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    assert row.slides[0].image_url == REPO_RAW_BASE + "a/1.webp"


async def test_window_excludes_future_and_pre_account_items(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(
        _items(
            {"id": "future", "notify_at": (NOW + timedelta(hours=1)).isoformat()},
            {"id": "old", "notify_at": (NOW - timedelta(days=30)).isoformat()},
            {"id": "now"},
        )
    )
    rows = await announcement_repository.list_for_user(
        admin.id, notify_from=NOW - timedelta(days=1), now=NOW
    )
    assert [r.id for r in rows] == ["now"]


async def test_mark_seen_keeps_the_first_timestamp(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(_items({"id": "a"}))
    await announcement_repository.mark_seen(admin.id, ["a"], NOW - timedelta(hours=20))
    await announcement_repository.mark_seen(admin.id, ["a"], NOW)

    [row] = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    assert row.seen_at == NOW - timedelta(hours=20)


async def test_mark_seen_ignores_unknown_ids(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(_items({"id": "a"}))
    await announcement_repository.mark_seen(admin.id, ["a", "gone"], NOW)

    [row] = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    assert row.seen


async def test_removing_from_feed_drops_views(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(_items({"id": "a"}))
    await announcement_repository.mark_seen(admin.id, ["a"], NOW)
    await announcement_repository.replace_all([])
    await announcement_repository.replace_all(_items({"id": "a"}))

    [row] = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    assert not row.seen


async def test_dismiss_keeps_the_first_seen_at_and_hides(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(_items({"id": "a"}, {"id": "b"}))
    await announcement_repository.mark_seen(admin.id, ["a"], NOW - timedelta(hours=2))
    await announcement_repository.dismiss(admin.id, ["a", "b", "gone"], NOW)

    rows = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    by_id = {r.id: r for r in rows}
    assert by_id["a"].seen_at == NOW - timedelta(hours=2)
    assert by_id["a"].dismissed_at == NOW
    assert by_id["b"].seen_at == NOW and by_id["b"].dismissed_at == NOW


async def test_url_label_round_trips(
    announcement_repository: AnnouncementRepository, admin: UserDto
) -> None:
    await announcement_repository.replace_all(
        _items(
            {
                "id": "a",
                "url": "https://t.me/remna_shop",
                "url_label": {"en": "Join"},
                "slides": [{"text": {"en": "x"}, "url_label": {"en": "Go"}}],
            }
        )
    )
    [row] = await announcement_repository.list_for_user(admin.id, notify_from=LONG_AGO, now=NOW)
    assert row.url_label == {"en": "Join"}
    assert row.slides[0].url_label == {"en": "Go"}
