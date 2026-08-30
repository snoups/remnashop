import pytest

from app.core.enums import Locale
from app.core.exceptions import NotFoundError
from app.modules.translations.repository import TranslationsRepository


async def test_seed_missing_inserts_only_absent_rows(
    translations_repository: TranslationsRepository,
) -> None:
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Overwritten?")

    entry = await translations_repository.get(Locale.EN, "command", "menu")

    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_update_value_leaves_default_untouched(
    translations_repository: TranslationsRepository,
) -> None:
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")

    updated = await translations_repository.update_value(Locale.EN, "command", "menu", "New text")

    assert updated.value == "New text"
    assert updated.default_value == "Open the main menu"


async def test_reset_value_restores_default(
    translations_repository: TranslationsRepository,
) -> None:
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translations_repository.update_value(Locale.EN, "command", "menu", "New text")

    reset = await translations_repository.reset_value(Locale.EN, "command", "menu")

    assert reset.value == "Open the main menu"


async def test_update_value_raises_not_found_for_missing_row(
    translations_repository: TranslationsRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await translations_repository.update_value(Locale.RU, "command", "menu", "New text")


async def test_reset_value_raises_not_found_for_missing_row(
    translations_repository: TranslationsRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await translations_repository.reset_value(Locale.RU, "command", "menu")


async def test_copy_locale_from_duplicates_rows_with_new_locale(
    translations_repository: TranslationsRepository,
) -> None:
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")

    await translations_repository.copy_locale_from(Locale.EN, Locale.RU)

    copied = await translations_repository.get(Locale.RU, "command", "menu")
    assert copied is not None
    assert copied.value == "Open the main menu"
    assert copied.default_value == "Open the main menu"


async def test_delete_locale_removes_only_that_locale(
    translations_repository: TranslationsRepository,
) -> None:
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translations_repository.copy_locale_from(Locale.EN, Locale.RU)

    await translations_repository.delete_locale(Locale.RU)

    assert await translations_repository.get(Locale.RU, "command", "menu") is None
    assert await translations_repository.get(Locale.EN, "command", "menu") is not None


async def test_get_fluent_text_by_locale_serializes_each_locale(
    translations_repository: TranslationsRepository,
) -> None:
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translations_repository.seed_missing(Locale.RU, "command", "menu", "Открыть главное меню")

    texts = await translations_repository.get_fluent_text_by_locale([Locale.EN, Locale.RU])

    assert texts[Locale.EN] == "command =\n    .menu = Open the main menu\n"
    assert texts[Locale.RU] == "command =\n    .menu = Открыть главное меню\n"
