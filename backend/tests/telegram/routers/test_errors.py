from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.dispatcher.event.telegram import TelegramEventObserver
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import AnswerCallbackQuery
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as AiogramUser
from aiogram_dialog import ShowMode, StartMode
from aiogram_dialog.api.exceptions import UnknownIntent

import app.telegram.routers.errors as errors
from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import Locale
from app.telegram.middlewares import setup_middlewares
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

    await on_lost_context(event, manager, MagicMock(is_blocked=False))

    event.update.callback_query.answer.assert_awaited_once_with()
    stale.delete.assert_awaited_once()
    manager.start.assert_awaited_once_with(
        MainMenu.MAIN, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )


async def test_a_menu_that_fails_to_reopen_does_not_raise_again() -> None:
    manager = MagicMock(start=AsyncMock(side_effect=RuntimeError("menu broken")))

    await on_lost_context(
        _callback_event(UnknownIntent("gone")), manager, MagicMock(is_blocked=False)
    )


@pytest.mark.parametrize("user", [None, MagicMock(is_blocked=True)])
async def test_a_lost_context_reopens_no_menu_without_a_usable_user(user: object) -> None:
    manager = MagicMock(start=AsyncMock())

    await on_lost_context(_callback_event(UnknownIntent("gone")), manager, user)  # type: ignore[arg-type]

    manager.start.assert_not_awaited()


async def test_an_error_raised_before_the_user_middleware_still_carries_the_user() -> None:
    # aiogram-dialog raises UnknownIntent from its own outer middleware, ahead of
    # UserMiddleware; the dialog manager holds the error event's data dict
    dispatcher = Dispatcher()
    dispatcher.observers["aiogd_update"] = TelegramEventObserver(
        router=dispatcher, event_name="aiogd_update"
    )

    async def lose_intent(handler: Any, event: Any, data: dict[str, Any]) -> Any:
        raise UnknownIntent("gone")

    dispatcher.callback_query.outer_middleware(lose_intent)
    manager_data: dict[str, Any] = {}

    async def hold_data(handler: Any, event: Any, data: dict[str, Any]) -> Any:
        manager_data["data"] = data
        return await handler(event, data)

    dispatcher.errors.outer_middleware(hold_data)
    setup_middlewares(dispatcher)

    async def on_error(event: object) -> None:
        pass

    dispatcher.errors.register(on_error)
    user = MagicMock()
    container = MagicMock(
        get=AsyncMock(return_value=MagicMock(system=AsyncMock(return_value=user)))
    )
    tg_user = AiogramUser(id=5, is_bot=False, first_name="")
    chat = Chat(id=5, type="private")
    update = Update(
        update_id=1,
        callback_query=CallbackQuery(
            id="1",
            from_user=tg_user,
            chat_instance="x",
            data="stale",
            message=Message(message_id=1, date=datetime.now(UTC), chat=chat),
        ),
    )

    await dispatcher.feed_update(MagicMock(spec=Bot, id=1), update, **{CONTAINER_KEY: container})

    assert manager_data["data"][USER_KEY] is user


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
