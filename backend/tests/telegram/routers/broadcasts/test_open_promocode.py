from unittest.mock import AsyncMock, MagicMock, patch

from aiogram_dialog import ShowMode, StartMode

from app.telegram.routers.broadcasts.handlers import _open_promocode
from app.telegram.states import MainMenu, Promocode


async def test_deeplink_puts_the_promocode_on_top_of_the_menu() -> None:
    manager = AsyncMock()
    with patch("app.telegram.routers.broadcasts.handlers.continue_with_code", AsyncMock()):
        opened = await _open_promocode(
            1,
            MagicMock(),
            manager,
            MagicMock(),
            AsyncMock(return_value="CODE"),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )

    assert opened
    starts = manager.start.await_args_list
    assert [c.args[0] for c in starts] == [MainMenu.MAIN, Promocode.INPUT]
    assert starts[0].kwargs == {"mode": StartMode.RESET_STACK, "show_mode": ShowMode.NO_UPDATE}
    assert starts[1].kwargs == {"show_mode": ShowMode.SEND}
