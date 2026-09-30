import pytest

from app.core.enums import ButtonLinkType, DialogFlow
from app.modules.dialogs import catalog


@pytest.fixture(autouse=True)
def _clean_catalog():
    catalog._reset_for_tests()
    yield
    catalog._reset_for_tests()


def test_register_and_snapshot_round_trip() -> None:
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name="menu",
            buttons=(
                catalog.CatalogButton(
                    key="subscription",
                    text_key="btn-menu.subscription",
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="subscription.main",
                ),
            ),
        )
    )
    snap = catalog.window_snapshot("menu.main")
    assert snap["banner_name"] == "menu"
    assert snap["buttons"][0]["key"] == "subscription"
    assert snap["buttons"][0]["link_type"] == "navigate"
    assert snap["buttons"][0]["is_hidden"] is False


def test_duplicate_window_key_raises() -> None:
    w = catalog.CatalogWindow(
        key="a", flow=DialogFlow.MENU, text_keys=(), banner_name=None, buttons=()
    )
    catalog.register_window(w)
    with pytest.raises(ValueError):
        catalog.register_window(w)


def test_action_key_registration_rejects_duplicates() -> None:
    catalog.register_action_key("buy")
    with pytest.raises(ValueError):
        catalog.register_action_key("buy")
    assert "buy" in catalog.action_keys()


def test_bind_action_handler_requires_registered_key() -> None:
    with pytest.raises(ValueError):
        catalog.bind_action_handler("buy", lambda: None)


def test_bind_action_handler_rejects_double_bind() -> None:
    catalog.register_action_key("buy")
    catalog.bind_action_handler("buy", lambda: None)
    with pytest.raises(ValueError):
        catalog.bind_action_handler("buy", lambda: None)


def test_has_action_handler() -> None:
    catalog.register_action_key("buy")
    assert catalog.has_action_handler("buy") is False
    catalog.bind_action_handler("buy", lambda: None)
    assert catalog.has_action_handler("buy") is True


def test_text_variable_keys_excludes_dotted_names() -> None:
    catalog.register_variable("name", lambda data: data.get("name", ""), category="user")
    catalog.register_variable(
        "subscription.url", lambda data: data.get("connect_url", ""), category="user"
    )
    assert catalog.text_variable_keys() == frozenset({"name"})


def test_text_variable_keys_accepts_hyphens_and_underscores() -> None:
    catalog.register_variable("device-count", lambda data: 0, category="user")
    catalog.register_variable("device_count", lambda data: 0, category="user")
    assert {"device-count", "device_count"} <= catalog.text_variable_keys()


@pytest.mark.parametrize("reserved", ["key", "self"])
def test_register_variable_rejects_reserved_names(reserved: str) -> None:
    with pytest.raises(ValueError):
        catalog.register_variable(reserved, lambda data: "", category="user")


def _register_menu_window() -> None:
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name=None,
            buttons=(
                catalog.CatalogButton(
                    key="subscription",
                    text_key="btn-menu.subscription",
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="subscription.main",
                ),
            ),
        )
    )


def test_text_keys_covers_window_bodies_and_button_labels() -> None:
    _register_menu_window()
    assert catalog.text_keys() == frozenset({"msg-main-menu", "btn-menu.subscription"})


def test_is_editable_text_key_accepts_catalog_and_custom_keys() -> None:
    _register_menu_window()
    assert catalog.is_editable_text_key("msg-main-menu")
    assert catalog.is_editable_text_key("btn-menu.subscription")
    assert catalog.is_editable_text_key(f"{catalog.CUSTOM_TEXT_KEY_PREFIX}anything")


def test_is_editable_text_key_rejects_rows_outside_the_dialogs_namespace() -> None:
    # command.start is a bot command description: documented as never
    # admin-editable, and reachable through import only while the allowlist is
    # derived from submitted button text_keys rather than from the catalog.
    _register_menu_window()
    assert not catalog.is_editable_text_key("command.start")
    assert not catalog.is_editable_text_key("ntf-subscription-expiring")
