from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import AnswerCallbackQuery
from aiogram.types import Message
from aiogram_dialog import ShowMode, StartMode
from aiogram_dialog.api.exceptions import UnknownIntent

import app.telegram.routers.errors as errors
from app.core.enums import Locale
from app.telegram.routers.errors import on_lost_context, on_unhandled_error
from app.telegram.states import MainMenu


def _i18n() -> MagicMock:
    runner = MagicMock(get=lambda key, **_: key)
    return MagicMock(get_translator_by_locale=MagicMock(return_value=runner))


def _callback_event(exception: Exception) -> MagicMock:
    event = MagicMock(exception=exception)
    event.update.callback_query.answer = AsyncMock()
    event.update.message = None
    return event


async def test_a_lost_context_silently_replaces_the_stale_window_with_the_menu() -> None:
    event = _callback_event(UnknownIntent("gone"))
    stale = MagicMock(spec=Message)
    stale.delete = AsyncMock()
    event.update.callback_query.message = stale
    manager = MagicMock(start=AsyncMock())

    await on_lost_context(event, manager)

    event.update.callback_query.answer.assert_awaited_once_with()
    stale.delete.assert_awaited_once()
    manager.start.assert_awaited_once_with(
        MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )


async def test_a_menu_that_fails_to_reopen_does_not_raise_again() -> None:
    manager = MagicMock(start=AsyncMock(side_effect=RuntimeError("menu broken")))

    await on_lost_context(_callback_event(UnknownIntent("gone")), manager)


def _shop(support_url: object = None) -> MagicMock:
    shop = MagicMock()
    shop.system = AsyncMock(return_value=MagicMock(support_link=support_url))
    return shop


async def _unhandled(event: MagicMock, manager: MagicMock, support_url: object = None) -> None:
    await on_unhandled_error(
        event, manager, _shop(support_url), _i18n(), user=MagicMock(language=Locale.EN)
    )


async def test_any_other_error_gets_a_message_and_the_menu() -> None:
    event = _callback_event(RuntimeError("boom"))
    manager = MagicMock(start=AsyncMock())

    await _unhandled(event, manager)

    event.update.callback_query.answer.assert_awaited_once_with("ntf-common.unknown-error")
    manager.start.assert_awaited_once_with(
        MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )


async def test_an_error_offers_support_when_it_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    notice = AsyncMock()
    monkeypatch.setattr(errors, "answer_notice", notice)

    await _unhandled(
        _callback_event(RuntimeError("boom")), MagicMock(start=AsyncMock()), "https://t.me/help"
    )

    keyboard = notice.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].url == "https://t.me/help"
    assert notice.await_args.kwargs["keep"] is True


async def test_an_error_in_start_does_not_reopen_the_menu() -> None:
    event = MagicMock(exception=RuntimeError("boom"))
    event.update.callback_query = None
    event.update.message.text = "/start"
    event.update.message.answer = AsyncMock()
    manager = MagicMock(start=AsyncMock())

    await _unhandled(event, manager)

    manager.start.assert_not_awaited()


async def test_a_menu_that_fails_after_an_error_does_not_raise() -> None:
    manager = MagicMock(start=AsyncMock(side_effect=RuntimeError("menu broken")))

    await _unhandled(_callback_event(RuntimeError("boom")), manager)


async def test_a_reply_telegram_refuses_is_swallowed() -> None:
    event = _callback_event(RuntimeError("boom"))
    event.update.callback_query.answer = AsyncMock(
        side_effect=TelegramForbiddenError(
            method=AnswerCallbackQuery(callback_query_id="1"), message="blocked"
        )
    )

    await _unhandled(event, MagicMock(start=AsyncMock()))
