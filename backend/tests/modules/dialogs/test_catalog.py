import pytest

from app.core.enums import BannerName, ButtonLinkType, DialogFlow
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
            banner_name=BannerName.MENU,
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


def test_action_registry_rejects_duplicates() -> None:
    catalog.register_action("buy", lambda: None)
    with pytest.raises(ValueError):
        catalog.register_action("buy", lambda: None)
    assert "buy" in catalog.action_keys()
