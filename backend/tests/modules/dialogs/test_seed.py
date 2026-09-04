import pytest

from app.core.enums import BannerName, ButtonLinkType, DialogFlow, Locale
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded


@pytest.fixture(autouse=True)
def _catalog():
    catalog._reset_for_tests()
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name=BannerName.MENU,
            buttons=(
                catalog.CatalogButton(
                    key="sub",
                    text_key="btn-menu.subscription",
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="subscription.main",
                ),
            ),
        )
    )
    yield
    catalog._reset_for_tests()


async def test_seed_is_idempotent(
    dialog_repository: DialogRepository, translations_repository, settings_repository
) -> None:
    await settings_repository.add_active_locale(Locale.EN)
    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)
    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    windows = await dialog_repository.list_all()
    assert [w.key for w in windows] == ["menu.main"]
    assert len(windows[0].buttons) == 1
    assert await translations_repository.get(Locale.EN, "btn-menu.subscription", "") is not None
