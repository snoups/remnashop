from pathlib import Path
from textwrap import dedent
from typing import Final

from fluent.syntax import FluentParser
from fluent.syntax.ast import Message, Pattern

from app.core.config import AppConfig
from app.core.enums import Locale
from app.core.exceptions import ConflictError
from app.modules.translations.repository import TranslationRepository

_SEED_DOMAINS: Final[tuple[str, ...]] = ("commands.ftl", "menu.ftl", "notifications.ftl")


def _parse_seed_file(path: Path) -> list[tuple[str, str, str]]:
    def pattern_text(source: str, pattern: object) -> str:
        assert isinstance(pattern, Pattern)
        assert pattern.span is not None
        # sliced from the source, not rebuilt from elements, so placeables and
        # multi-line values stay exactly as authored
        raw = source[pattern.span.start : pattern.span.end]
        first, separator, rest = raw.partition("\n")
        # The slice carries the .ftl's continuation indent; store the value
        # without it, so an editor shows the text the reader sees and
        # serialize_to_fluent() is the only thing that decides indentation.
        return first + separator + dedent(rest) if separator else raw

    source = path.read_text()
    resource = FluentParser().parse(source)
    entries: list[tuple[str, str, str]] = []
    for entry in resource.body:
        if not isinstance(entry, Message):
            continue
        message_id = entry.id.name
        if entry.value is not None:
            entries.append((message_id, "", pattern_text(source, entry.value)))
        for attribute in entry.attributes:
            entries.append((message_id, attribute.id.name, pattern_text(source, attribute.value)))
    return entries


def _read_seed_entries(config: AppConfig, locale: Locale) -> list[tuple[str, str, str]]:
    seed_files = [config.translations_dir / locale.value / domain for domain in _SEED_DOMAINS]
    return [
        entry
        for seed_file in seed_files
        if seed_file.is_file()
        for entry in _parse_seed_file(seed_file)
    ]


async def _fill_locales_without_seed(
    translation_repository: TranslationRepository,
    locales: set[Locale],
    en_entries: list[tuple[str, str, str]],
) -> None:
    # a locale added in the dashboard has no .ftl of its own: keys a release
    # adds reach it in English, otherwise its users hit KeyNotFoundError
    for locale in locales:
        await translation_repository.seed_missing_many(locale, en_entries)


async def ensure_translations_seeded(
    config: AppConfig,
    translation_repository: TranslationRepository,
) -> None:
    active_locales = set(await translation_repository.list_active_locales())
    first_boot = not active_locales
    shipped_locales: set[Locale] = set()
    en_entries: list[tuple[str, str, str]] = []

    for locale in Locale:
        entries = _read_seed_entries(config, locale)
        if not entries:
            continue
        shipped_locales.add(locale)
        if locale == Locale.EN:
            en_entries = entries

        if first_boot:
            try:
                await translation_repository.add_active_locale(locale)
            except ConflictError:
                pass
            active_locales.add(locale)

        if locale not in active_locales:
            continue

        await translation_repository.seed_missing_many(locale, entries)

    await _fill_locales_without_seed(
        translation_repository, active_locales - shipped_locales, en_entries
    )

    # also a database that predates the flag, or whose flagged row was lost
    if await translation_repository.find_default_locale() is None:
        active = await translation_repository.list_active_locales()
        if active:
            fallback = Locale.EN if Locale.EN in active else min(active, key=lambda x: x.value)
            await translation_repository.set_default_locale(fallback)
