import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, Message

import app.telegram.notice as notice
from app.telegram.notice import answer_notice


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notice, "_NOTICE_TTL_S", 0)


async def _drain() -> None:
    await asyncio.gather(*notice._deletions)


async def test_message_gets_an_italic_escaped_reply_that_is_deleted() -> None:
    sent = MagicMock(spec=Message)
    sent.delete = AsyncMock()
    message = MagicMock(spec=Message)
    message.answer = AsyncMock(return_value=sent)

    await answer_notice(message, "🚧 a < b")
    await _drain()

    message.answer.assert_awaited_once_with(
        "<i>🚧 a &lt; b</i>", parse_mode=ParseMode.HTML, reply_markup=None
    )
    sent.delete.assert_awaited_once()


async def test_button_press_gets_a_message_instead_of_an_alert() -> None:
    sent = MagicMock(spec=Message)
    sent.delete = AsyncMock()
    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=42)
    callback.bot = MagicMock()
    callback.bot.send_message = AsyncMock(return_value=sent)

    await answer_notice(callback, "❌ Denied.")
    await _drain()

    callback.answer.assert_awaited_once_with()
    callback.bot.send_message.assert_awaited_once_with(
        42, "<i>❌ Denied.</i>", parse_mode=ParseMode.HTML, reply_markup=None
    )
    sent.delete.assert_awaited_once()
