from types import SimpleNamespace

import pytest

from app.modules.dialogs import catalog
from app.telegram.dialogs import state_pool
from app.telegram.dialogs.catalog_menu import register_menu_catalog
from app.telegram.states import MainMenu


@pytest.fixture(autouse=True)
def _clean():
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    yield
    catalog._reset_for_tests()
    state_pool._reset_for_tests()


def test_registers_all_five_windows() -> None:
    register_menu_catalog()
    keys = {w.key for w in catalog.all_windows()}
    assert keys == {
        "menu.main",
        "menu.devices",
        "menu.device_confirm_delete",
        "menu.device_confirm_delete_all",
        "menu.device_confirm_reissue",
    }


def test_registers_actions_and_conditions() -> None:
    register_menu_catalog()
    actions = {"get_trial", "delete_device", "delete_all_devices", "reissue_subscription"}
    assert actions <= catalog.action_keys()
    conditions = {"trial_available", "has_device_limit", "connectable", "has_devices"}
    assert conditions <= catalog.condition_keys()
    assert "subscription_url" in catalog.variable_keys()


def test_binds_action_handlers() -> None:
    # This is what distinguishes register_menu_catalog() (telegram-only) from
    # register_menu_metadata() (pure, api-safe): only the former actually attaches
    # real callables.
    register_menu_catalog()
    assert catalog.has_action_handler("get_trial") is True
    assert catalog.has_action_handler("delete_device") is True
    assert catalog.has_action_handler("delete_all_devices") is True
    assert catalog.has_action_handler("reissue_subscription") is True


async def test_registers_seed_states() -> None:
    register_menu_catalog()

    class _FakeCache:
        async def custom_window_slot(self, key: str):
            return None

        async def get_window(self, key: str):
            return SimpleNamespace(is_enabled=True)

    resolved = await state_pool.resolve_state("menu.main", _FakeCache())
    assert resolved is MainMenu.MAIN


def test_calling_twice_is_idempotent() -> None:
    # Not just a nice-to-have: routers/menu/__init__.py's eager dual-import of
    # `dialog`/`handlers`, combined with dialog.py calling this function at its
    # own module level, means register_menu_catalog() can be re-entered as a
    # side effect of its own lazy handlers import on a cold process (a direct
    # call -- e.g. from this test file -- triggers the routers.menu package
    # init, which imports dialog.py, which calls this function again, nested,
    # before the outer call's own registration lines run). Both calls are the
    # same logical operation, so the second one is a no-op, not an error.
    register_menu_catalog()
    register_menu_catalog()
    assert {w.key for w in catalog.all_windows()} == {
        "menu.main",
        "menu.devices",
        "menu.device_confirm_delete",
        "menu.device_confirm_delete_all",
        "menu.device_confirm_reissue",
    }
    assert catalog.has_action_handler("get_trial") is True
