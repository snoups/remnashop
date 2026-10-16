from types import SimpleNamespace

import pytest

from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.dialogs import state_pool
from app.telegram.routers.menu.catalog import register_menu_catalog
from app.telegram.routers.subscriptions.catalog import register_subscriptions_catalog
from app.telegram.states import MainMenu, Subscriptions


@pytest.fixture(autouse=True)
def _clean():
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    yield
    catalog._reset_for_tests()
    state_pool._reset_for_tests()


def test_registers_all_windows() -> None:
    register_menu_catalog()
    keys = {w.key for w in catalog.all_windows()}
    assert keys == {
        "menu.main",
        "menu.devices",
        "menu.device_confirm_delete",
        "menu.device_confirm_delete_all",
        "menu.device_confirm_reissue",
        "subscriptions.list",
        "subscriptions.card",
        "referrals.main",
    }


def test_main_menu_offers_the_customer_sections() -> None:
    register_all_flow_metadata()
    keys = {button.key for button in catalog.get_window("menu.main").buttons}

    assert {"subscriptions", "purchase", "promocode", "referrals"} <= keys
    assert "devices" not in keys
    assert catalog.has_window("subscriptions.list")
    assert catalog.has_window("subscriptions.card")
    assert catalog.has_window("referrals.main")
    assert {
        "purchase_new",
        "purchase_renew",
        "purchase_change",
        "open_subscriptions",
        "promocode",
        "withdraw_points",
        "redeem_days",
    } <= catalog.action_keys()


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
    register_subscriptions_catalog()
    assert catalog.has_action_handler("get_trial") is True
    assert catalog.has_action_handler("open_subscriptions") is True
    assert catalog.has_action_handler("subscription_card_back") is True
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


async def test_subscriptions_catalog_registers_seed_states() -> None:
    register_subscriptions_catalog()

    class _FakeCache:
        async def custom_window_slot(self, key: str):
            return None

        async def get_window(self, key: str):
            return SimpleNamespace(is_enabled=True)

    cache = _FakeCache()
    assert await state_pool.resolve_state("subscriptions.list", cache) is Subscriptions.LIST
    assert await state_pool.resolve_state("subscriptions.card", cache) is Subscriptions.CARD
    assert await state_pool.resolve_state("menu.devices", cache) is Subscriptions.DEVICES


def test_card_back_is_its_own_action() -> None:
    # open_subscriptions reopens the card for a single subscription, so back can't reuse it
    register_all_flow_metadata()
    back = next(b for b in catalog.get_window("subscriptions.card").buttons if b.key == "back")
    assert back.action_key == "subscription_card_back"
    assert "subscription_card_back" in catalog.action_keys()


def test_calling_twice_is_idempotent() -> None:
    # dialog.py calls it at import time, tests call it again after a reset
    register_menu_catalog()
    register_menu_catalog()
    assert {w.key for w in catalog.all_windows()} == {
        "menu.main",
        "menu.devices",
        "menu.device_confirm_delete",
        "menu.device_confirm_delete_all",
        "menu.device_confirm_reissue",
        "subscriptions.list",
        "subscriptions.card",
        "referrals.main",
    }
    assert catalog.has_action_handler("get_trial") is True
