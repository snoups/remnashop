from dishka import Provider, Scope, provide, provide_all

from app.modules.translations.repository import TranslationRepository
from app.modules.translations.usecases import (
    AddLocaleUseCase,
    ExportTranslationsUseCase,
    ImportTranslationsUseCase,
    ListActiveLocalesUseCase,
    ListTranslationsUseCase,
    RemoveLocaleUseCase,
    ResetAllTranslationsUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)


class TranslationsProvider(Provider):
    scope = Scope.REQUEST

    translation_repository = provide(TranslationRepository)
    use_cases = provide_all(
        ListTranslationsUseCase,
        UpdateTranslationUseCase,
        ResetTranslationUseCase,
        ResetAllTranslationsUseCase,
        ExportTranslationsUseCase,
        ImportTranslationsUseCase,
        ListActiveLocalesUseCase,
        AddLocaleUseCase,
        RemoveLocaleUseCase,
    )


def get_translations_providers() -> list[Provider]:
    return [TranslationsProvider()]
