from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import User

from app.modules.users import UserDto
from app.telegram.routers.broadcasts.handlers import (
    on_broadcast_menu,
    on_broadcast_promocode,
    parse_broadcast_id,
    parse_start_broadcast_id,
)

_HANDLERS: Final[str] = "app.telegram.routers.broadcasts.handlers"


def test_parse_broadcast_id() -> None:
    assert parse_broadcast_id("bc:promo:12") == 12
    assert parse_broadcast_id("bc:promo:x") is None
    assert parse_broadcast_id("bc:promo:") is None


def test_parse_start_broadcast_id() -> None:
    assert parse_start_broadcast_id("bc_12") == 12
    assert parse_start_broadcast_id("bc_") is None
    assert parse_start_broadcast_id("bc_1x") is None
    assert parse_start_broadcast_id("ref_12") is None


def _press(data: str) -> AsyncMock:
    callback = AsyncMock()
    callback.data = data
    callback.from_user = User(id=777, is_bot=False, first_name="c")
    return callback


async def test_promocode_button_replays_the_start_deep_link_in_the_chat() -> None:
    callback = _press("bc:promo:12")
    get_code = AsyncMock(return_value="SALE")
    user = UserDto(name="c")

    with patch(f"{_HANDLERS}.replay_later") as replay:
        await on_broadcast_promocode(callback, MagicMock(), get_code, AsyncMock(), user=user)

    get_code.assert_awaited_once_with(user, 12)
    callback.answer.assert_awaited_once_with()
    message = replay.call_args.args[2]
    assert (message.text, message.chat.id) == ("/start bc_12", 777)


async def test_promocode_button_alerts_when_code_is_gone() -> None:
    callback = AsyncMock()
    callback.data = "bc:promo:12"
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value.get.return_value = "gone"

    await on_broadcast_promocode(
        callback, AsyncMock(), AsyncMock(return_value=None), i18n, user=UserDto(name="c")
    )

    callback.answer.assert_awaited_once_with("gone")


async def test_menu_button_replays_the_menu_start_in_the_chat() -> None:
    callback = _press("bc:menu")

    with patch(f"{_HANDLERS}.replay_later") as replay:
        await on_broadcast_menu(callback, MagicMock(), AsyncMock(), user=UserDto(name="c"))

    callback.answer.assert_awaited_once_with()
    message = replay.call_args.args[2]
    assert (message.text, message.from_user.id) == ("/start menu", 777)


def test_broadcast_ids_reject_non_ascii_digits_and_values_beyond_int32() -> None:
    assert parse_broadcast_id("bc:promo:¹") is None
    assert parse_broadcast_id(f"bc:promo:{2**31}") is None
    assert parse_start_broadcast_id(f"bc_{2**31}") is None
    assert parse_start_broadcast_id("bc_٤٢") is None
    assert parse_broadcast_id("bc:promo:42") == 42
