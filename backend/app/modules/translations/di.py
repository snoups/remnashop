from dishka import Provider, Scope, provide

from app.modules.translations.repository import TranslationsRepository
from app.modules.translations.usecases import (
    ListTranslationsUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)


class TranslationsProvider(Provider):
    scope = Scope.REQUEST

    translations_repository = provide(TranslationsRepository)
    list_translations_use_case = provide(ListTranslationsUseCase)
    update_translation_use_case = provide(UpdateTranslationUseCase)
    reset_translation_use_case = provide(ResetTranslationUseCase)


def get_translations_providers() -> list[Provider]:
    return [TranslationsProvider()]
