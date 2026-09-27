from typing import Optional

from app.modules.dialogs import catalog
from app.modules.dialogs.validation import validate_window_text
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository, join_message_key


async def validate_stored_window_texts(
    window_key: str,
    banner_name: Optional[str],
    translations_repository: TranslationsRepository,
    settings_repository: SettingsRepository,
) -> None:
    active = set(await settings_repository.list_active_locales())
    text_keys = set(catalog.window_text_keys(window_key))
    for entry in await translations_repository.list_all():
        if entry.locale not in active:
            continue
        if join_message_key(entry.message_id, entry.attribute_id) in text_keys:
            validate_window_text(
                entry.value, has_banner=banner_name is not None, locale=entry.locale
            )
