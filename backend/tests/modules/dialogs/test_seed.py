import pytest

from app.core.enums import ButtonLinkType, DialogFlow, Locale
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
            banner_name="menu",
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
    dialog_repository: DialogRepository, translation_repository, settings_repository
) -> None:
    # the shared dev database may have 'en' active already
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)
    await ensure_dialogs_seeded(dialog_repository, translation_repository)
    await ensure_dialogs_seeded(dialog_repository, translation_repository)

    windows = await dialog_repository.list_all()
    assert [w.key for w in windows] == ["menu.main"]
    assert len(windows[0].buttons) == 1
    # message "btn-menu", attribute "subscription": a dotted message id isn't valid Fluent
    assert await translation_repository.get(Locale.EN, "btn-menu", "subscription") is not None
    assert await translation_repository.get(Locale.EN, "btn-menu.subscription", "") is None


async def test_seed_orders_windows_the_way_the_catalog_registers_them(
    dialog_repository: DialogRepository, translation_repository, settings_repository
) -> None:
    # Both keys sort the other way round alphabetically, so a list that comes back
    # in flow order can only have come from the seeded positions.
    catalog._reset_for_tests()
    for key in ("menu.main", "menu.devices"):
        catalog.register_window(
            catalog.CatalogWindow(
                key=key, flow=DialogFlow.MENU, text_keys=("msg-main-menu",), banner_name=None
            )
        )

    await ensure_dialogs_seeded(dialog_repository, translation_repository)

    assert [w.key for w in await dialog_repository.list_all()] == ["menu.main", "menu.devices"]


async def test_seed_removes_the_shadow_row_an_older_seed_left(
    dialog_repository: DialogRepository, translation_repository, settings_repository
) -> None:
    # An earlier seed stored the dotted key as its own message id. That row wins
    # the joined-key lookup the editor builds, so button labels render blank.
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.seed_missing(Locale.EN, "btn-menu.subscription", "", "")

    await ensure_dialogs_seeded(dialog_repository, translation_repository)

    assert await translation_repository.get(Locale.EN, "btn-menu.subscription", "") is None


async def test_seed_keeps_an_edited_shadow_row(
    dialog_repository: DialogRepository, translation_repository, settings_repository
) -> None:
    # same row shape, but someone typed into it, so it stays
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.seed_missing(
        Locale.EN, "btn-menu.subscription", "", "Typed by hand"
    )

    await ensure_dialogs_seeded(dialog_repository, translation_repository)

    kept = await translation_repository.get(Locale.EN, "btn-menu.subscription", "")
    assert kept is not None
    assert kept.value == "Typed by hand"
