from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import AnswerCallbackQuery
from aiogram_dialog import ShowMode, StartMode
from aiogram_dialog.api.exceptions import UnknownIntent

from app.core.enums import Locale
from app.telegram.routers.errors import on_lost_context, on_unhandled_error
from app.telegram.states import MainMenu


def _i18n() -> MagicMock:
    runner = MagicMock(get=lambda key, **_: key)
    return MagicMock(get_translator_by_locale=MagicMock(return_value=runner))


def _callback_event(exception: Exception) -> MagicMock:
    event = MagicMock(exception=exception)
    event.update.callback_query.answer = AsyncMock()
    return event


async def test_a_lost_context_answers_the_button_and_reopens_the_menu() -> None:
    event = _callback_event(UnknownIntent("gone"))
    manager = MagicMock(start=AsyncMock())

    await on_lost_context(event, manager, _i18n(), user=MagicMock(language=Locale.EN))

    event.update.callback_query.answer.assert_awaited_once_with(
        "ntf-common.lost-context", show_alert=True
    )
    manager.start.assert_awaited_once_with(
        MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )


async def test_a_menu_that_fails_to_reopen_does_not_raise_again() -> None:
    manager = MagicMock(start=AsyncMock(side_effect=RuntimeError("menu broken")))

    await on_lost_context(
        _callback_event(UnknownIntent("gone")),
        manager,
        _i18n(),
        user=MagicMock(language=Locale.EN),
    )


async def test_any_other_error_gets_a_message_and_no_menu() -> None:
    event = _callback_event(RuntimeError("boom"))

    await on_unhandled_error(event, _i18n(), user=MagicMock(language=Locale.EN))

    event.update.callback_query.answer.assert_awaited_once_with(
        "ntf-common.unknown-error", show_alert=True
    )


async def test_a_reply_telegram_refuses_is_swallowed() -> None:
    event = _callback_event(RuntimeError("boom"))
    event.update.callback_query.answer = AsyncMock(
        side_effect=TelegramForbiddenError(
            method=AnswerCallbackQuery(callback_query_id="1"), message="blocked"
        )
    )

    await on_unhandled_error(event, _i18n(), user=MagicMock(language=Locale.EN))
