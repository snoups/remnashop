import sys

import pytest

from app.modules.dialogs import catalog


@pytest.fixture(autouse=True)
def _clean():
    catalog._reset_for_tests()
    yield
    catalog._reset_for_tests()


def test_importable_without_aiogram(monkeypatch: pytest.MonkeyPatch) -> None:
    # The entire point of this package: it must not need aiogram to import.
    # Simulate aiogram being absent (as it genuinely is in the api process's
    # Docker image) rather than merely unused.
    for name in list(sys.modules):
        if name == "aiogram" or name.startswith("aiogram."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "aiogram", None)

    monkeypatch.delitem(sys.modules, "app.modules.dialogs.flows.menu", raising=False)
    from app.modules.dialogs.flows.menu import register_menu_metadata  # noqa: PLC0415

    register_menu_metadata()
    assert catalog.has_window("menu.main")


def test_register_menu_metadata_populates_full_catalog() -> None:
    from app.modules.dialogs.flows.menu import register_menu_metadata  # noqa: PLC0415

    register_menu_metadata()

    keys = {w.key for w in catalog.all_windows()}
    assert keys == {
        "menu.main",
        "menu.devices",
        "menu.device_confirm_delete",
        "menu.device_confirm_delete_all",
        "menu.device_confirm_reissue",
    }
    assert {
        "get_trial",
        "delete_device",
        "delete_all_devices",
        "reissue_subscription",
    } <= catalog.action_keys()
    assert {
        "trial_available",
        "has_device_limit",
        "connectable",
        "has_devices",
    } <= catalog.condition_keys()
    assert "subscription.url" in catalog.variable_keys()
    # This is the parity regression test: no handler is bound anywhere here,
    # yet the keys are fully visible -- exactly what the api process needs.
    assert catalog.has_action_handler("get_trial") is False


def test_register_menu_metadata_is_idempotent() -> None:
    from app.modules.dialogs.flows.menu import register_menu_metadata  # noqa: PLC0415

    register_menu_metadata()
    register_menu_metadata()
    assert len(catalog.all_windows()) == 5


def test_register_all_flow_metadata_calls_menu() -> None:
    from app.modules.dialogs.flows import register_all_flow_metadata  # noqa: PLC0415

    register_all_flow_metadata()
    assert catalog.has_window("menu.main")
