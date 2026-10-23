import json
from datetime import timedelta
from typing import Any, Union

import httpx
import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.utils.time import datetime_now
from app.modules.announcements.dto import AnnouncementIdsDto
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.announcements.usecases import (
    ListAnnouncementsUseCase,
    MarkAnnouncementsSeenUseCase,
    SyncAnnouncementsUseCase,
)
from app.modules.announcements.usecases import sync_announcements as sync_module
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


def _feed(*items: dict[str, Any]) -> bytes:
    now = datetime_now()
    base = {"title": {"en": "t"}, "notify_at": (now + timedelta(seconds=1)).isoformat()}
    return json.dumps({"items": [{**base, **i} for i in items]}).encode()


def _serve(monkeypatch: pytest.MonkeyPatch, body: Union[bytes, Exception]) -> None:
    async def fake_fetch(url: str = "") -> bytes:
        if isinstance(body, Exception):
            raise body
        return body

    monkeypatch.setattr(sync_module, "fetch_feed", fake_fetch)


@pytest.fixture
async def admin(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        return await user_repository.create(CreateUserDto(login="adm", name="adm", role=Role.ADMIN))


async def _sync(repo: AnnouncementRepository, uow: UnitOfWork) -> None:
    await SyncAnnouncementsUseCase(repo, uow).system()


async def _all_ids(repo: AnnouncementRepository, user: UserDto) -> list[str]:
    rows = await repo.list_for_user(
        user.id,
        notify_from=datetime_now() - timedelta(days=1),
        now=datetime_now() + timedelta(days=1),
    )
    return sorted(r.id for r in rows)


async def test_sync_mirrors_the_feed(
    monkeypatch: pytest.MonkeyPatch,
    announcement_repository: AnnouncementRepository,
    uow: UnitOfWork,
    admin: UserDto,
) -> None:
    _serve(monkeypatch, _feed({"id": "a"}, {"id": "b"}))
    await _sync(announcement_repository, uow)
    assert await _all_ids(announcement_repository, admin) == ["a", "b"]


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("down"), b"<html>rate limited</html>", b'{"oops": 1}'],
)
async def test_failed_sync_keeps_the_current_set(
    monkeypatch: pytest.MonkeyPatch,
    announcement_repository: AnnouncementRepository,
    uow: UnitOfWork,
    admin: UserDto,
    failure: Union[bytes, Exception],
) -> None:
    _serve(monkeypatch, _feed({"id": "a"}))
    await _sync(announcement_repository, uow)
    _serve(monkeypatch, failure)
    await _sync(announcement_repository, uow)
    assert await _all_ids(announcement_repository, admin) == ["a"]


async def test_list_applies_visibility_and_mark_hides_after_a_day(
    monkeypatch: pytest.MonkeyPatch,
    announcement_repository: AnnouncementRepository,
    uow: UnitOfWork,
    admin: UserDto,
    config: AppConfig,
) -> None:
    # admin was created just now; items notify 1s later, so they are inside the window
    _serve(monkeypatch, _feed({"id": "all"}, {"id": "owners", "roles": ["OWNER"]}))
    await _sync(announcement_repository, uow)
    monkeypatch.setattr(
        "app.modules.announcements.usecases.list_announcements.datetime_now",
        lambda: datetime_now() + timedelta(minutes=1),
    )

    listed = await ListAnnouncementsUseCase(announcement_repository, uow, config)(admin)
    assert [a.id for a in listed] == ["all"]

    await MarkAnnouncementsSeenUseCase(announcement_repository, uow)(
        admin, AnnouncementIdsDto(ids=["all"])
    )
    monkeypatch.setattr(
        "app.modules.announcements.usecases.list_announcements.datetime_now",
        lambda: datetime_now() + timedelta(days=2),
    )
    assert await ListAnnouncementsUseCase(announcement_repository, uow, config)(admin) == []
