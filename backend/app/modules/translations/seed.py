from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from app.core.config import AppConfig
from app.core.enums import Locale
from app.core.exceptions import ConflictError
from app.modules.translations.repository import TranslationsRepository

if TYPE_CHECKING:
    from app.modules.settings import SettingsRepository

_SEED_DOMAIN: Final[str] = "commands.ftl"


def _parse_seed_file(path: Path) -> list[tuple[str, str, str]]:
    # Lazy import -- fluent.syntax ships with fluent_compiler, which lives
    # under the `telegram` extra, same reason command_translations.py lazily
    # imports fluent_compiler/fluentogram: don't load it on every api-process
    # import, only when seeding actually runs.
    from fluent.syntax import FluentParser  # noqa: PLC0415
    from fluent.syntax.ast import Message, Placeable  # noqa: PLC0415

    def pattern_text(pattern: object) -> str:
        from fluent.syntax.ast import Pattern, TextElement  # noqa: PLC0415

        assert isinstance(pattern, Pattern)
        parts: list[str] = []
        for element in pattern.elements:
            if isinstance(element, Placeable):
                raise ValueError("Fluent placeables are not supported in seed files")
            assert isinstance(element, TextElement)
            parts.append(element.value)
        return "".join(parts)

    resource = FluentParser().parse(path.read_text())
    entries: list[tuple[str, str, str]] = []
    for entry in resource.body:
        if not isinstance(entry, Message):
            continue
        message_id = entry.id.name
        if entry.value is not None:
            entries.append((message_id, "", pattern_text(entry.value)))
        for attribute in entry.attributes:
            entries.append((message_id, attribute.id.name, pattern_text(attribute.value)))
    return entries


async def ensure_translations_seeded(
    config: AppConfig,
    translations_repository: TranslationsRepository,
    settings_repository: SettingsRepository,
) -> None:
    active_locales = set(await settings_repository.list_active_locales())
    first_boot = not active_locales

    for locale in Locale:
        seed_file = config.translations_dir / locale.value / _SEED_DOMAIN
        if not seed_file.is_file():
            continue

        if first_boot:
            try:
                await settings_repository.add_active_locale(locale)
            except ConflictError:
                pass
            active_locales.add(locale)

        if locale not in active_locales:
            continue

        for message_id, attribute_id, value in _parse_seed_file(seed_file):
            await translations_repository.seed_missing(locale, message_id, attribute_id, value)
