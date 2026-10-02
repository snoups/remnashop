import pytest

from app.core.enums import Locale
from app.core.exceptions import ConflictError
from app.modules.translations.repository import TranslationRepository


async def test_add_and_list_active_locales(translation_repository: TranslationRepository) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.add_active_locale(Locale.RU)

    locales = await translation_repository.list_active_locales()

    assert set(locales) == {Locale.EN, Locale.RU}


async def test_add_active_locale_rejects_duplicate(
    translation_repository: TranslationRepository,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)

    with pytest.raises(ConflictError):
        await translation_repository.add_active_locale(Locale.EN)


async def test_remove_active_locale(translation_repository: TranslationRepository) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.add_active_locale(Locale.RU)

    await translation_repository.remove_active_locale(Locale.RU)

    assert await translation_repository.list_active_locales() == [Locale.EN]
