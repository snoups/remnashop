from typing import Any, Optional

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import RetryableTaskError
from app.modules.notifications.dto import DeliverNotificationDto, PushMessage
from app.modules.notifications.render import NotificationRenderer
from app.modules.notifications.usecases import DeliverNotificationUseCase
from app.modules.notifications.usecases import deliver as deliver_module
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

FTL = (
    "ntf-login-failed = Wrong password for { $login }\n    .title = Login failed\n"
    "ntf-suppressed = { $count } more not sent.\n"
    "ntf-sources-merged = Sources merged.\n"
)
BLOCKED_CHAT: int = 403
BROKEN_CHAT: int = 500


class FakePush:
    def __init__(self) -> None:
        self.sent: list[tuple[int, PushMessage]] = []

    async def send(self, user_id: int, message: PushMessage) -> int:
        self.sent.append((user_id, message))
        return 1


class FakeRendererFactory:
    async def build(self) -> NotificationRenderer:
        return NotificationRenderer({Locale.EN: FTL}, default_locale=Locale.EN)


class FakeBotTokenSource:
    def __init__(self, token: Optional[str]) -> None:
        self._token = token

    async def get_bot_token(self) -> tuple[Optional[str], Optional[str]]:
        return self._token, None


async def _staff(repo: UserRepository, uow: UnitOfWork, login: str, **extra: Any) -> UserDto:
    # one OWNER per database, so extra recipients are admins granted the bell
    return await _user(
        repo, uow, login, Role.ADMIN, permission_grants=["NOTIFICATIONS_VIEW"], **extra
    )


async def _user(
    repo: UserRepository, uow: UnitOfWork, login: str, role: Role, **extra: Any
) -> UserDto:
    async with uow:
        return await repo.create(
            CreateUserDto(login=login, name=login, role=role, language=Locale.EN, **extra)
        )


@pytest.fixture
def telegram_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    calls: list[tuple[int, str]] = []

    async def fake_send(token: str, proxy: Optional[str], chat_id: int, text: str) -> bool:
        calls.append((chat_id, text))
        if chat_id == BROKEN_CHAT:
            raise RuntimeError("unexpected client error")
        return chat_id != BLOCKED_CHAT

    monkeypatch.setattr(deliver_module, "send_telegram_message", fake_send)
    return calls


def _use_case(
    user_repository: UserRepository, uow: UnitOfWork, push: FakePush, token: Optional[str]
) -> DeliverNotificationUseCase:
    return DeliverNotificationUseCase(
        user_repository,
        uow,
        push,  # type: ignore[arg-type]
        FakeRendererFactory(),  # type: ignore[arg-type]
        FakeBotTokenSource(token),  # type: ignore[arg-type]
    )


def _login_failed(actor_id: Optional[int] = None) -> DeliverNotificationDto:
    return DeliverNotificationDto(
        event_type="LoginFailedEvent", payload={"login": "x"}, actor_id=actor_id, ip_address=None
    )


async def test_delivers_to_permitted_staff_except_the_actor(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    owner = await _user(user_repository, uow, "owner", Role.OWNER)
    actor = await _staff(user_repository, uow, "actor")
    plain_admin = await _user(user_repository, uow, "plain", Role.ADMIN)
    granted_admin = await _user(
        user_repository, uow, "granted", Role.ADMIN, permission_grants=["NOTIFICATIONS_VIEW"]
    )
    customer = await _user(user_repository, uow, "cust", Role.USER)
    push = FakePush()

    await _use_case(user_repository, uow, push, "token").system(_login_failed(actor.id))

    recipients = {user_id for user_id, _ in push.sent}
    assert {owner.id, granted_admin.id} <= recipients
    assert recipients.isdisjoint({actor.id, plain_admin.id, customer.id})
    message = next(m for user_id, m in push.sent if user_id == owner.id)
    assert (message.title, message.body) == ("Login failed", "Wrong password for x")
    assert message.url == "/dashboard?bell=open"
    assert message.tag == "LoginFailedEvent"


async def test_revoked_permission_and_switched_off_channel_get_nothing(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    revoked = await _user(
        user_repository, uow, "revoked", Role.OWNER, permission_revokes=["NOTIFICATIONS_VIEW"]
    )
    quiet = await _staff(user_repository, uow, "quiet")
    async with uow:
        await user_repository.set_notification_channels(quiet.id, {"security": ["bell"]})
    push = FakePush()

    await _use_case(user_repository, uow, push, "token").system(_login_failed())

    assert {user_id for user_id, _ in push.sent}.isdisjoint({revoked.id, quiet.id})


async def test_telegram_refusal_does_not_stop_other_deliveries(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    blocked = await _user(user_repository, uow, "blocked", Role.OWNER, telegram_id=BLOCKED_CHAT)
    other = await _staff(user_repository, uow, "other", telegram_id=777)
    push = FakePush()

    await _use_case(user_repository, uow, push, "token").system(_login_failed())

    assert {chat for chat, _ in telegram_calls} >= {BLOCKED_CHAT, 777}
    assert {user_id for user_id, _ in push.sent} >= {blocked.id, other.id}
    assert telegram_calls[0][1] == "Login failed\n\nWrong password for x"


async def test_no_bot_token_skips_telegram(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    await _user(user_repository, uow, "owner", Role.OWNER, telegram_id=777)
    await _use_case(user_repository, uow, FakePush(), None).system(_login_failed())
    assert telegram_calls == []


async def test_event_outside_groups_is_ignored(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    await _user(user_repository, uow, "owner", Role.OWNER)
    push = FakePush()
    await _use_case(user_repository, uow, push, "token").system(
        DeliverNotificationDto(
            event_type="LoginSucceededEvent", payload={}, actor_id=None, ip_address=None
        )
    )
    assert push.sent == []


async def test_unexpected_telegram_error_does_not_stop_other_admins(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    await _user(user_repository, uow, "owner", Role.OWNER, telegram_id=BROKEN_CHAT)
    await _staff(user_repository, uow, "other", telegram_id=777)

    await _use_case(user_repository, uow, FakePush(), "token").system(_login_failed())

    assert {chat for chat, _ in telegram_calls} == {BROKEN_CHAT, 777}


async def test_long_body_is_cut_for_both_channels(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    await _user(user_repository, uow, "owner", Role.OWNER, telegram_id=777)
    push = FakePush()

    await _use_case(user_repository, uow, push, "token").system(
        DeliverNotificationDto(
            event_type="LoginFailedEvent",
            payload={"login": "x" * 5000},
            actor_id=None,
            ip_address=None,
        )
    )

    [(_, message)] = push.sent
    assert len(message.body) <= deliver_module.MAX_BODY_LENGTH
    assert len(telegram_calls[0][1]) <= deliver_module.MAX_BODY_LENGTH + 100


async def test_failure_before_sending_is_retryable(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    await _user(user_repository, uow, "owner", Role.OWNER)

    class BrokenFactory:
        async def build(self) -> NotificationRenderer:
            raise ConnectionError("translations unreachable")

    use_case = DeliverNotificationUseCase(
        user_repository,
        uow,
        FakePush(),  # type: ignore[arg-type]
        BrokenFactory(),  # type: ignore[arg-type]
        FakeBotTokenSource("token"),  # type: ignore[arg-type]
    )

    with pytest.raises(RetryableTaskError):
        await use_case.system(_login_failed())


async def test_suppressed_count_is_appended_to_the_body(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    owner = await _user(user_repository, uow, "owner", Role.OWNER)
    push = FakePush()
    data = DeliverNotificationDto(
        event_type="LoginFailedEvent",
        payload={"login": "x"},
        actor_id=None,
        ip_address=None,
        suppressed=3,
    )

    await _use_case(user_repository, uow, push, None).system(data)

    message = next(m for user_id, m in push.sent if user_id == owner.id)
    assert message.body == "Wrong password for x\n3 more not sent."


async def test_a_merged_window_says_so_in_the_body(
    user_repository: UserRepository, uow: UnitOfWork, telegram_calls: list[tuple[int, str]]
) -> None:
    owner = await _user(user_repository, uow, "owner", Role.OWNER)
    push = FakePush()
    data = DeliverNotificationDto(
        event_type="LoginFailedEvent",
        payload={"login": "x"},
        actor_id=None,
        ip_address=None,
        sources_merged=True,
    )

    await _use_case(user_repository, uow, push, None).system(data)

    message = next(m for user_id, m in push.sent if user_id == owner.id)
    assert message.body == "Wrong password for x\nSources merged."
