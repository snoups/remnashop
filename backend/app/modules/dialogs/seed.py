from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository, split_message_key


async def ensure_dialogs_seeded(
    dialog_repository: DialogRepository,
    translations_repository: TranslationsRepository,
    settings_repository: SettingsRepository,
) -> None:
    locales = await settings_repository.list_active_locales()
    for position, window in enumerate(catalog.all_windows()):
        await dialog_repository.upsert_seed(
            window.key,
            window.flow,
            window.banner_name,
            catalog.window_snapshot(window.key),
            position=position,
        )
        text_keys = set(window.text_keys) | {b.text_key for b in window.buttons}
        for locale in locales:
            for text_key in text_keys:
                message_id, attribute_id = split_message_key(text_key)
                await translations_repository.seed_missing(locale, message_id, attribute_id, "")
                if attribute_id:
                    # Earlier seeds stored the dotted key as a message id of its
                    # own, which shadows the real row everywhere the two are
                    # looked up by joined key.
                    await translations_repository.delete_blank(locale, text_key, "")
