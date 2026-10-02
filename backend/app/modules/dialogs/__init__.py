"""Dialog configuration module."""

from app.modules.dialogs import catalog
from app.modules.dialogs.di import DialogsProvider, get_dialogs_providers
from app.modules.dialogs.dto import (
    ConfigureDialogWindowDto,
    CreateCustomDialogWindowDto,
    CreateCustomWindowDto,
    DialogButtonDto,
    DialogButtonInputDto,
    DialogCatalogDto,
    DialogExportDto,
    DialogTextExportDto,
    DialogWindowDto,
    DialogWindowExportDto,
    UpdateDialogWindowButtonsDto,
    UpdateDialogWindowDto,
)
from app.modules.dialogs.flows import register_all_flow_metadata
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    ExportDialogsUseCase,
    GetDialogCatalogUseCase,
    ImportDialogsUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowUseCase,
)

__all__ = [
    "ConfigureDialogWindowDto",
    "CreateCustomDialogWindowDto",
    "CreateCustomDialogWindowUseCase",
    "CreateCustomWindowDto",
    "DeleteCustomDialogWindowUseCase",
    "DialogButtonDto",
    "DialogButtonInputDto",
    "DialogCatalogDto",
    "DialogExportDto",
    "DialogRepository",
    "DialogTextExportDto",
    "DialogWindowDto",
    "DialogWindowExportDto",
    "DialogsProvider",
    "ExportDialogsUseCase",
    "GetDialogCatalogUseCase",
    "ImportDialogsUseCase",
    "ListDialogWindowsUseCase",
    "ResetAllDialogsUseCase",
    "ResetDialogWindowUseCase",
    "UpdateDialogWindowButtonsDto",
    "UpdateDialogWindowButtonsUseCase",
    "UpdateDialogWindowDto",
    "UpdateDialogWindowUseCase",
    "catalog",
    "ensure_dialogs_seeded",
    "get_dialogs_providers",
    "register_all_flow_metadata",
]
