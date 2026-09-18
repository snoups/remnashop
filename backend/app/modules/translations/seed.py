from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final

from app.core.config import AppConfig
from app.core.enums import Locale
from app.core.exceptions import ConflictError
from app.modules.translations.repository import TranslationsRepository

if TYPE_CHECKING:
    from app.modules.settings import SettingsRepository

_SEED_DOMAINS: Final[tuple[str, ...]] = ("commands.ftl", "menu.ftl")


def _parse_seed_file(path: Path) -> list[tuple[str, str, str]]:
    # Lazy import -- fluent.syntax ships with fluent_compiler, which lives
    # under the `telegram` extra, same reason command_translations.py lazily
    # imports fluent_compiler/fluentogram: don't load it on every api-process
    # import, only when seeding actually runs.
    from fluent.syntax import FluentParser  # noqa: PLC0415
    from fluent.syntax.ast import Message, Pattern  # noqa: PLC0415

    def pattern_text(source: str, pattern: object) -> str:
        assert isinstance(pattern, Pattern)
        assert pattern.span is not None
        # Slice the original source rather than walk elements -- preserves
        # placeables ({ $var }) and multi-line continuation exactly as
        # authored, instead of reconstructing (and rejecting) them by hand.
        raw = source[pattern.span.start : pattern.span.end]
        first, separator, rest = raw.partition("\n")
        # The slice carries the .ftl's own continuation indent; store the value
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


async def ensure_translations_seeded(
    config: AppConfig,
    translations_repository: TranslationsRepository,
    settings_repository: SettingsRepository,
) -> None:
    active_locales = set(await settings_repository.list_active_locales())
    first_boot = not active_locales

    for locale in Locale:
        seed_files = [config.translations_dir / locale.value / domain for domain in _SEED_DOMAINS]
        seed_files = [seed_file for seed_file in seed_files if seed_file.is_file()]
        if not seed_files:
            continue

        if first_boot:
            try:
                await settings_repository.add_active_locale(locale)
            except ConflictError:
                pass
            active_locales.add(locale)

        if locale not in active_locales:
            continue

        for seed_file in seed_files:
            for message_id, attribute_id, value in _parse_seed_file(seed_file):
                await translations_repository.seed_missing(locale, message_id, attribute_id, value)
