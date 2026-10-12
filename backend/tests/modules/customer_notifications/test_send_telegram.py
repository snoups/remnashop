from typing import Any, Final, Optional, cast

import pytest

from app.core.db.uow import UnitOfWork
from app.core.exceptions import RetryableTaskError
from app.modules.customer_notifications.dto import SendCustomerTelegramDto
from app.modules.customer_notifications.usecases import send_customer_telegram
from app.modules.customer_notifications.usecases.send_customer_telegram import (
    SendCustomerTelegramUseCase,
)
from app.modules.notifications import TelegramSendResult
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

_RESULT: Final[dict[str, TelegramSendResult]] = {}


class _Tokens:
    def __init__(self, token: Optional[str]) -> None:
        self._token = token

    async def get_bot_token(self) -> tuple[Optional[str], None]:
        return self._token, None


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    calls: list[tuple[int, str]] = []
    _RESULT["value"] = TelegramSendResult.SENT

    async def _send(
        token: str, proxy: object, chat_id: int, text: str, **kwargs: object
    ) -> TelegramSendResult:
        calls.append((chat_id, text))
        return _RESULT["value"]

    monkeypatch.setattr(send_customer_telegram, "send_telegram_text", _send)
    return calls


async def _run(users: UserRepository, uow: UnitOfWork, token: Optional[str], **fields: Any) -> None:
    async with uow:
        user: UserDto = await users.create(CreateUserDto(name="a", **fields))
        await uow.commit()
    use_case = SendCustomerTelegramUseCase(users, cast(Any, _Tokens(token)), uow)
    await use_case.system(SendCustomerTelegramDto(user_id=user.id, text="hi"))


async def test_failed_send_is_retryable(
    user_repository: UserRepository, uow: UnitOfWork, sent: list[tuple[int, str]]
) -> None:
    _RESULT["value"] = TelegramSendResult.FAILED
    with pytest.raises(RetryableTaskError):
        await _run(user_repository, uow, "t", telegram_id=9001)
    assert sent == [(9001, "hi")]


async def test_forbidden_is_final(
    user_repository: UserRepository, uow: UnitOfWork, sent: list[tuple[int, str]]
) -> None:
    _RESULT["value"] = TelegramSendResult.FORBIDDEN
    await _run(user_repository, uow, "t", telegram_id=9002)
    assert sent == [(9002, "hi")]


async def test_no_token_sends_nothing(
    user_repository: UserRepository, uow: UnitOfWork, sent: list[tuple[int, str]]
) -> None:
    await _run(user_repository, uow, None, telegram_id=9003)
    assert sent == []


async def test_user_without_telegram_sends_nothing(
    user_repository: UserRepository, uow: UnitOfWork, sent: list[tuple[int, str]]
) -> None:
    await _run(user_repository, uow, "t", email="a@example.com")
    assert sent == []
