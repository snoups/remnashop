import pytest

from app.core.enums import Locale
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded
from app.telegram.dialogs import state_pool
from app.telegram.routers.menu.catalog import register_menu_catalog


@pytest.fixture(autouse=True)
def _clean():
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    yield
    catalog._reset_for_tests()
    state_pool._reset_for_tests()


async def test_ensure_dialogs_seeded_seeds_real_menu_windows(
    dialog_repository: DialogRepository, translation_repository, settings_repository
) -> None:
    register_menu_catalog()
    # the shared dev database may already have 'en' active; checking first is
    # simpler than recovering the session after a ConflictError
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)

    await ensure_dialogs_seeded(dialog_repository, translation_repository)

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
