from dishka import Provider, Scope, provide, provide_all

from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    ExportDialogsUseCase,
    GetDialogCatalogUseCase,
    ImportDialogsUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogTextUseCase,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowUseCase,
)


class DialogsProvider(Provider):
    scope = Scope.REQUEST

    dialog_repository = provide(DialogRepository)
    use_cases = provide_all(
        ListDialogWindowsUseCase,
        GetDialogCatalogUseCase,
        UpdateDialogTextUseCase,
        UpdateDialogWindowUseCase,
        UpdateDialogWindowButtonsUseCase,
        CreateCustomDialogWindowUseCase,
        DeleteCustomDialogWindowUseCase,
        ResetDialogWindowUseCase,
        ResetAllDialogsUseCase,
        ExportDialogsUseCase,
        ImportDialogsUseCase,
    )


def get_dialogs_providers() -> list[Provider]:
    return [DialogsProvider()]
