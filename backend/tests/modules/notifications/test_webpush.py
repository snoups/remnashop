import json
from typing import Any

import pytest
from pywebpush import WebPushException
from requests import Response

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.modules.auth.repository import SessionRepository
from app.modules.notifications import webpush as webpush_module
from app.modules.notifications.dto import PushMessage
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.vapid import generate_vapid_keypair
from app.modules.notifications.webpush import WebPushSender
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.notifications.conftest import NewSession

MESSAGE = PushMessage(title="t", body="b", url="/dashboard?bell=open", tag="LoginFailedEvent")


def _error(status: int) -> WebPushException:
    response = Response()
    response.status_code = status
    return WebPushException("push failed", response=response)


@pytest.fixture
async def subscribed(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="o", name="o", role=Role.OWNER, language=Locale.EN)
        )
        await notification_repository.set_vapid_keys(*generate_vapid_keypair())
        await notification_repository.upsert_push_subscription(
            user_id=user.id,
            session_id=await new_session(user.id),
            endpoint="https://push.example/1",
            p256dh="k",
            auth="a",
            user_agent=None,
        )
    return user


async def test_gone_endpoint_is_deleted(
    subscribed: UserDto,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_webpush(**kwargs: Any) -> None:
        raise _error(410)

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    delivered = await WebPushSender(notification_repository, uow).send(
        subscribed.id, MESSAGE, SessionAudience.DASHBOARD
    )

    assert delivered == 0
    assert (
        await notification_repository.list_push_subscriptions(
            subscribed.id, SessionAudience.DASHBOARD
        )
        == []
    )


async def test_third_failure_deletes_and_success_resets(
    subscribed: UserDto,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes = iter([_error(500), None, _error(500), _error(500), _error(500)])

    def fake_webpush(**kwargs: Any) -> None:
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    sender = WebPushSender(notification_repository, uow)

    await sender.send(subscribed.id, MESSAGE, SessionAudience.DASHBOARD)
    assert await sender.send(subscribed.id, MESSAGE, SessionAudience.DASHBOARD) == 1
    [sub] = await notification_repository.list_push_subscriptions(
        subscribed.id, SessionAudience.DASHBOARD
    )
    assert sub.failure_count == 0
    for _ in range(3):
        await sender.send(subscribed.id, MESSAGE, SessionAudience.DASHBOARD)
    assert (
        await notification_repository.list_push_subscriptions(
            subscribed.id, SessionAudience.DASHBOARD
        )
        == []
    )


async def test_not_configured_sends_nothing(
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_webpush(**kwargs: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    assert (
        await WebPushSender(notification_repository, uow).send(
            1, MESSAGE, SessionAudience.DASHBOARD
        )
        == 0
    )
    assert not called


async def test_payload_too_large_keeps_the_device(
    subscribed: UserDto,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_webpush(**kwargs: Any) -> None:
        raise _error(413)

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    sender = WebPushSender(notification_repository, uow)
    for _ in range(3):
        await sender.send(subscribed.id, MESSAGE, SessionAudience.DASHBOARD)

    [sub] = await notification_repository.list_push_subscriptions(
        subscribed.id, SessionAudience.DASHBOARD
    )
    assert sub.failure_count == 0


async def test_push_does_not_follow_redirects(
    subscribed: UserDto,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_webpush(**kwargs: Any) -> None:
        seen.update(kwargs)

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    await WebPushSender(notification_repository, uow).send(
        subscribed.id, MESSAGE, SessionAudience.DASHBOARD
    )

    assert seen["requests_session"].max_redirects == 0


async def test_revoked_session_stops_its_pushes(
    subscribed: UserDto,
    notification_repository: NotificationRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []

    def fake_webpush(**kwargs: Any) -> None:
        sent.append(kwargs["subscription_info"]["endpoint"])

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    async with uow:
        await session_repository.revoke_all_by_user(subscribed.id)

    assert (
        await WebPushSender(notification_repository, uow).send(
            subscribed.id, MESSAGE, SessionAudience.DASHBOARD
        )
        == 0
    )
    assert sent == []
    assert (
        await notification_repository.list_push_subscriptions(
            subscribed.id, SessionAudience.DASHBOARD
        )
        == []
    )


async def test_send_includes_icon_when_set(
    subscribed: UserDto,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[dict[str, Any]] = []

    def fake_webpush(**kwargs: Any) -> None:
        payloads.append(json.loads(kwargs["data"]))

    monkeypatch.setattr(webpush_module, "webpush", fake_webpush)
    async with uow:
        await notification_repository.upsert_push_subscription(
            user_id=subscribed.id,
            session_id=await new_session(subscribed.id, SessionAudience.CABINET),
            endpoint="https://push.example/cabinet",
            p256dh="k",
            auth="a",
            user_agent=None,
        )
    sender = WebPushSender(notification_repository, uow)
    icon = "/api/appearance/cabinet/favicon?v=1"

    await sender.send(
        subscribed.id,
        PushMessage(title="t", body="b", url="/", tag="x", icon=icon),
        SessionAudience.CABINET,
    )
    await sender.send(subscribed.id, MESSAGE, SessionAudience.CABINET)

    assert payloads[0]["icon"] == icon
    assert "icon" not in payloads[1]


async def test_deliver_skips_cabinet_subscriptions(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webpush_module, "webpush", lambda **kwargs: None)
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(login="a", name="a", role=Role.OWNER, language=Locale.EN)
        )
        await notification_repository.set_vapid_keys(*generate_vapid_keypair())
        await notification_repository.upsert_push_subscription(
            user_id=admin.id,
            session_id=await new_session(admin.id, SessionAudience.CABINET),
            endpoint="https://push.example/cabinet",
            p256dh="k",
            auth="a",
            user_agent=None,
        )

    sender = WebPushSender(notification_repository, uow)
    assert await sender.send(admin.id, MESSAGE, SessionAudience.DASHBOARD) == 0
    assert await sender.send(admin.id, MESSAGE, SessionAudience.CABINET) == 1
