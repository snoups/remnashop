from typing import Final, Optional, Protocol

from aiogram.fsm.state import State, StatesGroup


class CustomWindows(StatesGroup):
    W0 = State()
    W1 = State()
    W2 = State()
    W3 = State()
    W4 = State()
    W5 = State()
    W6 = State()
    W7 = State()
    W8 = State()
    W9 = State()
    W10 = State()
    W11 = State()
    W12 = State()
    W13 = State()
    W14 = State()
    W15 = State()
    W16 = State()
    W17 = State()
    W18 = State()
    W19 = State()
    W20 = State()
    W21 = State()
    W22 = State()
    W23 = State()
    W24 = State()
    W25 = State()
    W26 = State()
    W27 = State()
    W28 = State()
    W29 = State()
    W30 = State()
    W31 = State()
    W32 = State()
    W33 = State()
    W34 = State()
    W35 = State()
    W36 = State()
    W37 = State()
    W38 = State()
    W39 = State()
    W40 = State()
    W41 = State()
    W42 = State()
    W43 = State()
    W44 = State()
    W45 = State()
    W46 = State()
    W47 = State()
    W48 = State()
    W49 = State()


# fixed pool of 50 custom-window states, raise the cap if a shop needs more


_CUSTOM_WINDOW_STATES: Final[tuple[State, ...]] = tuple(
    getattr(CustomWindows, f"W{i}") for i in range(50)
)

_SEED_STATES: Final[dict[str, State]] = {}


class _EnabledWindow(Protocol):
    is_enabled: bool


class _SlotResolver(Protocol):
    async def custom_window_slot(self, window_key: str) -> Optional[int]: ...
    async def get_window(self, key: str) -> _EnabledWindow: ...


def register_seed_state(window_key: str, state: State) -> None:
    if window_key in _SEED_STATES:
        raise ValueError(f"Duplicate seed state registration: {window_key}")
    _SEED_STATES[window_key] = state


async def resolve_state(window_key: str, cache: _SlotResolver) -> Optional[State]:
    try:
        window = await cache.get_window(window_key)
    except KeyError:
        return None
    if not window.is_enabled:
        return None

    if window_key in _SEED_STATES:
        return _SEED_STATES[window_key]
    slot = await cache.custom_window_slot(window_key)
    if slot is None or not 0 <= slot < len(_CUSTOM_WINDOW_STATES):
        return None
    return _CUSTOM_WINDOW_STATES[slot]


def _reset_for_tests() -> None:
    # test-only: catalog_*.py modules register seed states at import time and are never
    # unregistered in prod, same rationale as app.modules.dialogs.catalog._reset_for_tests
    _SEED_STATES.clear()
