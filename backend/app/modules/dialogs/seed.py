from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository


async def ensure_dialogs_seeded(
    dialog_repository: DialogRepository,
    translations_repository: TranslationsRepository,
    settings_repository: SettingsRepository,
) -> None:
    locales = await settings_repository.list_active_locales()
    for window in catalog.all_windows():
        await dialog_repository.upsert_seed(
            window.key, window.flow, window.banner_name, catalog.window_snapshot(window.key)
        )
        text_keys = set(window.text_keys) | {b.text_key for b in window.buttons}
        for locale in locales:
            for message_id in text_keys:
                await translations_repository.seed_missing(locale, message_id, "", "")
