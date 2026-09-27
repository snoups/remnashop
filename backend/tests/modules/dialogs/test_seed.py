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
    dialog_repository: DialogRepository, translations_repository, settings_repository
) -> None:
    # This test runs against a real, shared dev database (not necessarily empty --
    # the real api/telegram services may have already activated 'en'), so check
    # first rather than assuming a pristine locale table.
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)
    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    windows = await dialog_repository.list_all()
    assert [w.key for w in windows] == ["menu.main"]
    assert len(windows[0].buttons) == 1
    # "btn-menu.subscription" is message "btn-menu", attribute "subscription" --
    # not a message id containing a dot, which is not even valid Fluent.
    assert await translations_repository.get(Locale.EN, "btn-menu", "subscription") is not None
    assert await translations_repository.get(Locale.EN, "btn-menu.subscription", "") is None


async def test_seed_orders_windows_the_way_the_catalog_registers_them(
    dialog_repository: DialogRepository, translations_repository, settings_repository
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

    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    assert [w.key for w in await dialog_repository.list_all()] == ["menu.main", "menu.devices"]


async def test_seed_removes_the_shadow_row_an_older_seed_left(
    dialog_repository: DialogRepository, translations_repository, settings_repository
) -> None:
    # An earlier seed stored the dotted key as its own message id. That row wins
    # the joined-key lookup the editor builds, so button labels render blank.
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "btn-menu.subscription", "", "")

    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    assert await translations_repository.get(Locale.EN, "btn-menu.subscription", "") is None


async def test_seed_keeps_an_edited_shadow_row(
    dialog_repository: DialogRepository, translations_repository, settings_repository
) -> None:
    # Same shape of row, but somebody typed into it -- dropping it would throw
    # away their text, so it stays for a human to deal with.
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(
        Locale.EN, "btn-menu.subscription", "", "Typed by hand"
    )

    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    kept = await translations_repository.get(Locale.EN, "btn-menu.subscription", "")
    assert kept is not None
    assert kept.value == "Typed by hand"
