from types import SimpleNamespace
from typing import Optional

import pytest
from aiogram.fsm.state import State, StatesGroup

from app.telegram.dialogs import state_pool


class _S(StatesGroup):
    MAIN = State()


class _FakeCache:
    def __init__(
        self,
        slots: dict[str, int],
        *,
        disabled: frozenset[str] = frozenset(),
        known: frozenset[str] = frozenset(),
    ) -> None:
        self._slots = slots
        self._disabled = disabled
        self._known = known | set(slots) | disabled

    async def custom_window_slot(self, key: str) -> Optional[int]:
        return self._slots.get(key)

    async def get_window(self, key: str) -> SimpleNamespace:
        if key not in self._known:
            raise KeyError(key)
        return SimpleNamespace(is_enabled=key not in self._disabled)


@pytest.fixture(autouse=True)
def _clean_state_pool():
    state_pool._reset_for_tests()
    yield
    state_pool._reset_for_tests()


async def test_resolve_seed_state() -> None:
    state_pool.register_seed_state("menu.main", _S.MAIN)
    resolved = await state_pool.resolve_state(
        "menu.main", _FakeCache({}, known=frozenset({"menu.main"}))
    )
    assert resolved is _S.MAIN


async def test_resolve_custom_window_state_by_slot() -> None:
    resolved = await state_pool.resolve_state("custom.abc", _FakeCache({"custom.abc": 2}))
    assert resolved is state_pool.CustomWindows.W2


async def test_resolve_unknown_window_returns_none() -> None:
    resolved = await state_pool.resolve_state("no.such.window", _FakeCache({}))
    assert resolved is None


async def test_resolve_out_of_range_slot_returns_none() -> None:
    resolved = await state_pool.resolve_state("custom.abc", _FakeCache({"custom.abc": 50}))
    assert resolved is None


async def test_resolve_disabled_window_returns_none() -> None:
    state_pool.register_seed_state("menu.main", _S.MAIN)
    cache = _FakeCache({}, disabled=frozenset({"menu.main"}))
    resolved = await state_pool.resolve_state("menu.main", cache)
    assert resolved is None


def test_duplicate_seed_state_registration_raises() -> None:
    state_pool.register_seed_state("menu.main", _S.MAIN)
    with pytest.raises(ValueError):
        state_pool.register_seed_state("menu.main", _S.MAIN)


def test_custom_window_pool_has_fifty_states() -> None:
    assert len(state_pool._CUSTOM_WINDOW_STATES) == 50
    assert state_pool._CUSTOM_WINDOW_STATES[0] is state_pool.CustomWindows.W0
    assert state_pool._CUSTOM_WINDOW_STATES[49] is state_pool.CustomWindows.W49
