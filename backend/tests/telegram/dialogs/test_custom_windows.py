from typing import Optional

import pytest
from aiogram_dialog import Dialog

from app.core.constants import CUSTOM_DIALOG_WINDOW_SLOTS
from app.telegram.dialogs import state_pool
from app.telegram.dialogs.state_pool import (
    CustomWindows,
    custom_window_states,
    resolve_custom_window_key,
)
from app.telegram.routers.custom.dialog import router as custom_dialog_router
from app.telegram.states import MainMenu


class _FakeCache:
    def __init__(self, keys_by_slot: dict[int, str]) -> None:
        self._keys_by_slot = keys_by_slot

    async def key_for_slot(self, slot: int) -> Optional[str]:
        return self._keys_by_slot.get(slot)


@pytest.fixture(autouse=True)
def _clean_state_pool():
    state_pool._reset_for_tests()
    yield
    state_pool._reset_for_tests()


async def test_resolve_custom_window_key_maps_state_back_to_its_window() -> None:
    cache = _FakeCache({3: "custom.faq"})

    assert await resolve_custom_window_key(CustomWindows.W3, cache) == "custom.faq"
    assert await resolve_custom_window_key(CustomWindows.W4, cache) is None


async def test_resolve_custom_window_key_ignores_a_seed_state() -> None:
    assert await resolve_custom_window_key(MainMenu.MAIN, _FakeCache({0: "custom.faq"})) is None


def test_every_pooled_state_has_a_window_registered() -> None:
    # Without this the dashboard can create a window the bot cannot show: the
    # button resolves to a state no dialog owns, and the user gets an error.
    assert isinstance(custom_dialog_router, Dialog)
    registered = {window.state for window in custom_dialog_router.windows.values()}

    assert registered == set(custom_window_states())
    assert len(registered) == CUSTOM_DIALOG_WINDOW_SLOTS
