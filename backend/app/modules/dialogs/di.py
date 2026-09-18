from dishka import Provider, Scope, provide

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
    list_dialog_windows_use_case = provide(ListDialogWindowsUseCase)
    get_dialog_catalog_use_case = provide(GetDialogCatalogUseCase)
    update_dialog_text_use_case = provide(UpdateDialogTextUseCase)
    update_dialog_window_use_case = provide(UpdateDialogWindowUseCase)
    update_dialog_window_buttons_use_case = provide(UpdateDialogWindowButtonsUseCase)
    create_custom_dialog_window_use_case = provide(CreateCustomDialogWindowUseCase)
    delete_custom_dialog_window_use_case = provide(DeleteCustomDialogWindowUseCase)
    reset_dialog_window_use_case = provide(ResetDialogWindowUseCase)
    reset_all_dialogs_use_case = provide(ResetAllDialogsUseCase)
    export_dialogs_use_case = provide(ExportDialogsUseCase)
    import_dialogs_use_case = provide(ImportDialogsUseCase)


def get_dialogs_providers() -> list[Provider]:
    return [DialogsProvider()]
