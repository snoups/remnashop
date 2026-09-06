"""Dialog configuration module."""

from app.modules.dialogs import catalog
from app.modules.dialogs.di import DialogsProvider, get_dialogs_providers
from app.modules.dialogs.dto import (
    CreateCustomWindowDto,
    DialogButtonDto,
    DialogButtonInputDto,
    DialogCatalogDto,
    DialogWindowDto,
    UpdateDialogWindowDto,
)
from app.modules.dialogs.flows import register_all_flow_metadata
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowInput,
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    GetDialogCatalogUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogWindowButtonsInput,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowInput,
    UpdateDialogWindowUseCase,
)

__all__ = [
    "CreateCustomDialogWindowInput",
    "CreateCustomDialogWindowUseCase",
    "CreateCustomWindowDto",
    "DeleteCustomDialogWindowUseCase",
    "DialogButtonDto",
    "DialogButtonInputDto",
    "DialogCatalogDto",
    "DialogRepository",
    "DialogsProvider",
    "DialogWindowDto",
    "GetDialogCatalogUseCase",
    "ListDialogWindowsUseCase",
    "ResetAllDialogsUseCase",
    "ResetDialogWindowUseCase",
    "UpdateDialogWindowButtonsInput",
    "UpdateDialogWindowButtonsUseCase",
    "UpdateDialogWindowDto",
    "UpdateDialogWindowInput",
    "UpdateDialogWindowUseCase",
    "catalog",
    "ensure_dialogs_seeded",
    "get_dialogs_providers",
    "register_all_flow_metadata",
]
