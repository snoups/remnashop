from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage

from app.telegram.middlewares.garbage import GarbageMiddleware


def _message(text: Optional[str], *, paid: bool = False) -> MagicMock:
    message = MagicMock(text=text, successful_payment=MagicMock() if paid else None)
    message.delete = AsyncMock()
    return message


async def _run(message: MagicMock) -> Any:
    handler = AsyncMock(return_value="handled")
    result = await GarbageMiddleware().middleware_logic(handler, message, {})
    handler.assert_awaited_once()
    return result


@pytest.mark.parametrize(
    ("text", "paid", "deleted"),
    [
        ("PROMO10", False, True),
        (None, False, True),  # a sticker or a photo
        ("/start", False, False),
        ("/start plan_abc", False, False),
        (None, True, False),  # the payment receipt stays
    ],
)
async def test_typed_messages_go_once_handled(
    text: Optional[str], paid: bool, deleted: bool
) -> None:
    message = _message(text, paid=paid)

    assert await _run(message) == "handled"
    assert message.delete.await_count == (1 if deleted else 0)


async def test_a_message_telegram_won_t_delete_is_still_handled() -> None:
    message = _message("too old")
    message.delete = AsyncMock(
        side_effect=TelegramBadRequest(
            method=DeleteMessage(chat_id=1, message_id=1), message="message can't be deleted"
        )
    )

    assert await _run(message) == "handled"
