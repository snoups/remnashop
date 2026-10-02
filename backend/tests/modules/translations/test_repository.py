import pytest

from app.core.enums import Locale
from app.core.exceptions import NotFoundError
from app.modules.translations.repository import TranslationRepository


async def test_seed_missing_inserts_only_absent_rows(
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Overwritten?")

    entry = await translation_repository.get(Locale.EN, "command", "menu")

    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_update_value_leaves_default_untouched(
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")

    updated = await translation_repository.update_value(Locale.EN, "command", "menu", "New text")

    assert updated.value == "New text"
    assert updated.default_value == "Open the main menu"


async def test_reset_value_restores_default(
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translation_repository.update_value(Locale.EN, "command", "menu", "New text")

    reset = await translation_repository.reset_value(Locale.EN, "command", "menu")

    assert reset.value == "Open the main menu"


async def test_update_value_raises_not_found_for_missing_row(
    translation_repository: TranslationRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await translation_repository.update_value(Locale.RU, "command", "menu", "New text")


async def test_reset_value_raises_not_found_for_missing_row(
    translation_repository: TranslationRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await translation_repository.reset_value(Locale.RU, "command", "menu")


async def test_copy_locale_from_duplicates_rows_with_new_locale(
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")

    await translation_repository.copy_locale_from(Locale.EN, Locale.RU)

    copied = await translation_repository.get(Locale.RU, "command", "menu")
    assert copied is not None
    assert copied.value == "Open the main menu"
    assert copied.default_value == "Open the main menu"


async def test_get_fluent_text_by_locale_serializes_each_locale(
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translation_repository.seed_missing(Locale.RU, "command", "menu", "Открыть главное меню")

    texts = await translation_repository.get_fluent_text_by_locale([Locale.EN, Locale.RU])

    assert texts[Locale.EN] == "command =\n    .menu = Open the main menu\n"
    assert texts[Locale.RU] == "command =\n    .menu = Открыть главное меню\n"
