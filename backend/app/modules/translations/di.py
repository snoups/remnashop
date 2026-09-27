from dishka import Provider, Scope, provide

from app.modules.translations.repository import TranslationsRepository
from app.modules.translations.usecases import (
    ExportTranslationsUseCase,
    ImportTranslationsUseCase,
    ListTranslationsUseCase,
    ResetAllTranslationsUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)


class TranslationsProvider(Provider):
    scope = Scope.REQUEST

    translations_repository = provide(TranslationsRepository)
    list_translations_use_case = provide(ListTranslationsUseCase)
    update_translation_use_case = provide(UpdateTranslationUseCase)
    reset_translation_use_case = provide(ResetTranslationUseCase)
    reset_all_translations_use_case = provide(ResetAllTranslationsUseCase)
    export_translations_use_case = provide(ExportTranslationsUseCase)
    import_translations_use_case = provide(ImportTranslationsUseCase)


def get_translations_providers() -> list[Provider]:
    return [TranslationsProvider()]
