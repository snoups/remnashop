from pathlib import Path
from typing import Final

from app.core.constants import ASSETS_DIR
from app.core.enums import Locale
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.seed import _parse_seed_file
from app.modules.translations.serializer import serialize_to_fluent

TRANSLATIONS_DIR: Final[Path] = ASSETS_DIR / "translations"


def seeded_fluent_source(locale: Locale, *files: str) -> str:
    """A locale's .ftl files as the bot reads them in production: seeded into
    rows, then serialized back from the database."""
    paths = [TRANSLATIONS_DIR / locale.value / name for name in files] or sorted(
        (TRANSLATIONS_DIR / locale.value).glob("*.ftl")
    )
    return serialize_to_fluent(
        [
            TranslationEntryDto(
                locale=locale,
                message_id=message_id,
                attribute_id=attribute_id,
                value=value,
                default_value=value,
            )
            for path in paths
            for message_id, attribute_id, value in _parse_seed_file(path)
        ]
    )
