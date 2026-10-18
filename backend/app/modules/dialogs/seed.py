from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.translations import TranslationRepository, split_message_key


async def ensure_dialogs_seeded(
    dialog_repository: DialogRepository,
    translation_repository: TranslationRepository,
) -> None:
    locales = await translation_repository.list_active_locales()
    for position, window in enumerate(catalog.all_windows()):
        await dialog_repository.upsert_seed(
            window.key,
            window.flow,
            window.banner_name,
            catalog.window_snapshot(window.key),
            position=position,
        )
        text_keys = sorted(set(window.text_keys) | {b.text_key for b in window.buttons})
        rows = [(*split_message_key(text_key), "") for text_key in text_keys]
        # Earlier seeds stored a dotted key as a message id of its own, which
        # shadows the real row everywhere the two are looked up by joined key.
        dotted = [
            text_key for text_key, (_, attribute_id, _) in zip(text_keys, rows) if attribute_id
        ]
        for locale in locales:
            await translation_repository.seed_missing_many(locale, rows)
            await translation_repository.delete_blank_messages(locale, dotted)
