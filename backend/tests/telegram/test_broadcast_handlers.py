from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.modules.users import UserDto
from app.telegram.routers.broadcasts.handlers import (
    on_broadcast_menu,
    on_broadcast_promocode,
    parse_broadcast_id,
    parse_start_broadcast_id,
)


def test_parse_broadcast_id() -> None:
    assert parse_broadcast_id("bc:promo:12") == 12
    assert parse_broadcast_id("bc:promo:x") is None
    assert parse_broadcast_id("bc:promo:") is None


def test_parse_start_broadcast_id() -> None:
    assert parse_start_broadcast_id("bc_12") == 12
    assert parse_start_broadcast_id("bc_") is None
    assert parse_start_broadcast_id("bc_1x") is None
    assert parse_start_broadcast_id("ref_12") is None


async def test_promocode_button_answers_with_start_deep_link() -> None:
    callback = AsyncMock()
    callback.data = "bc:promo:12"
    bot = AsyncMock()
    bot.me.return_value = SimpleNamespace(username="shop_bot")
    get_code = AsyncMock(return_value="SALE")
    user = UserDto(name="c")

    await on_broadcast_promocode(callback, bot, get_code, AsyncMock(), user=user)

    get_code.assert_awaited_once_with(user, 12)
    callback.answer.assert_awaited_once_with(url="https://t.me/shop_bot?start=bc_12")


async def test_promocode_button_alerts_when_code_is_gone() -> None:
    callback = AsyncMock()
    callback.data = "bc:promo:12"
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value.get.return_value = "gone"

    await on_broadcast_promocode(
        callback, AsyncMock(), AsyncMock(return_value=None), i18n, user=UserDto(name="c")
    )

    callback.answer.assert_awaited_once_with("gone", show_alert=True)


async def test_menu_button_answers_with_start_deep_link() -> None:
    callback = AsyncMock()
    bot = AsyncMock()
    bot.me.return_value = SimpleNamespace(username="shop_bot")

    await on_broadcast_menu(callback, bot, AsyncMock(), user=UserDto(name="c"))

    callback.answer.assert_awaited_once_with(url="https://t.me/shop_bot?start=menu")


def test_broadcast_ids_reject_non_ascii_digits_and_values_beyond_int32() -> None:
    assert parse_broadcast_id("bc:promo:¹") is None
    assert parse_broadcast_id(f"bc:promo:{2**31}") is None
    assert parse_start_broadcast_id(f"bc_{2**31}") is None
    assert parse_start_broadcast_id("bc_٤٢") is None
    assert parse_broadcast_id("bc:promo:42") == 42
