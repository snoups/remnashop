from typing import Any, cast

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.notifications.dto import SendTelegramTextsDto
from app.modules.notifications.render import NotificationRenderer
from app.modules.notifications.telegram import TelegramSendResult
from app.modules.notifications.usecases import send_telegram_texts
from app.modules.notifications.usecases.send_telegram_texts import SendTelegramTextsUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

_FTL = "ntf-access =\n    .payments-restored = Back!\n"
_KEY = "ntf-access.payments-restored"


class _Tokens:
    def __init__(self, token: Any) -> None:
        self._token = token

    async def get_bot_token(self) -> tuple[Any, None]:
        return self._token, None


class _Renderers:
    async def build(self) -> NotificationRenderer:
        return NotificationRenderer({Locale.EN: _FTL}, default_locale=Locale.EN)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    calls: list[tuple[int, str]] = []

    async def _send(
        token: str, proxy: object, chat_id: int, text: str, **kwargs: object
    ) -> TelegramSendResult:
        calls.append((chat_id, text))
        if chat_id == 7003:
            return TelegramSendResult.FAILED
        if chat_id == 7005:
            return TelegramSendResult.FORBIDDEN
        return TelegramSendResult.SENT

    monkeypatch.setattr(send_telegram_texts, "send_telegram_text", _send)
    monkeypatch.setattr(send_telegram_texts, "_SEND_PAUSE_S", 0)
    return calls


def _use_case(
    user_repository: UserRepository, uow: UnitOfWork, token: Any
) -> SendTelegramTextsUseCase:
    return SendTelegramTextsUseCase(
        user_repository, uow, cast(Any, _Tokens(token)), cast(Any, _Renderers())
    )


async def _create(user_repository: UserRepository, uow: UnitOfWork, **fields: Any) -> UserDto:
    async with uow:
        user = await user_repository.create(CreateUserDto(**fields))
        await uow.commit()
    return user


async def test_sends_rendered_text_and_reports_finished_ids(
    user_repository: UserRepository, uow: UnitOfWork, sent: list[tuple[int, str]]
) -> None:
    ok = await _create(user_repository, uow, name="a", telegram_id=7001)
    no_tg = await _create(user_repository, uow, name="b")
    failed = await _create(user_repository, uow, name="c", telegram_id=7003)
    blocked = await _create(user_repository, uow, name="d", telegram_id=7004, is_blocked=True)
    bot_blocked = await _create(user_repository, uow, name="e", telegram_id=7005)

    done = await _use_case(user_repository, uow, "t").system(
        SendTelegramTextsDto(
            user_ids=[ok.id, no_tg.id, failed.id, blocked.id, bot_blocked.id, 999_999], key=_KEY
        )
    )

    assert sorted(sent) == [(7001, "Back!"), (7003, "Back!"), (7005, "Back!")]
    # blocking the bot is permanent: no point keeping them for the next broadcast
    assert done == {ok.id, no_tg.id, blocked.id, bot_blocked.id, 999_999}


async def test_no_bot_means_nothing_is_done(
    user_repository: UserRepository, uow: UnitOfWork, sent: list[tuple[int, str]]
) -> None:
    user = await _create(user_repository, uow, name="a", telegram_id=7101)

    done = await _use_case(user_repository, uow, None).system(
        SendTelegramTextsDto(user_ids=[user.id], key=_KEY)
    )

    assert done == set()
    assert sent == []
