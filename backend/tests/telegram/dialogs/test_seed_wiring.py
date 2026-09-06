import pytest

from app.core.enums import Locale
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded
from app.telegram.dialogs import state_pool
from app.telegram.dialogs.catalog_menu import register_menu_catalog


@pytest.fixture(autouse=True)
def _clean():
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    yield
    catalog._reset_for_tests()
    state_pool._reset_for_tests()


async def test_ensure_dialogs_seeded_seeds_real_menu_windows(
    dialog_repository: DialogRepository, translations_repository, settings_repository
) -> None:
    register_menu_catalog()
    # This test runs against a real, shared dev database (not necessarily empty --
    # the real api/telegram services may have already activated 'en'), so check
    # first rather than assuming a pristine locale table and catching the
    # resulting ConflictError (which leaves the session needing an explicit
    # rollback before it can be used again -- avoiding the conflict in the
    # first place is simpler than recovering from it).
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)

    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    # Superset check, not exact-set: this runs against a real, shared dev database
    # that may already carry other windows seeded by other test runs or services.
    windows = await dialog_repository.list_all()
    assert {w.key for w in windows} >= {
        "menu.main",
        "menu.devices",
        "menu.device_confirm_delete",
        "menu.device_confirm_delete_all",
        "menu.device_confirm_reissue",
    }
