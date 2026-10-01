from app.core.actor import Actor
from app.core.constants import CUSTOM_DIALOG_WINDOW_SLOTS
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogCatalogDto
from app.modules.dialogs.repository import DialogRepository


class GetDialogCatalogUseCase(UseCase[None, DialogCatalogDto]):
    required_permission = Permission.DIALOGS_CATALOG_VIEW

    def __init__(self, dialog_repository: DialogRepository, uow: UnitOfWork) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> DialogCatalogDto:
        async with self._uow:
            windows = await self._dialog_repository.list_all()
            navigable = sorted({w.key for w in windows} | {w.key for w in catalog.all_windows()})
            return DialogCatalogDto(
                action_keys=sorted(catalog.action_keys()),
                condition_keys=sorted(catalog.condition_keys()),
                variable_keys=sorted(catalog.variable_keys()),
                text_variable_keys=sorted(catalog.text_variable_keys()),
                window_text_variable_keys={
                    w.key: list(w.text_variables) for w in catalog.all_windows() if w.text_variables
                },
                variable_categories=catalog.variable_categories(),
                seed_window_keys=sorted(w.key for w in catalog.all_windows()),
                navigable_window_keys=navigable,
                custom_window_limit=CUSTOM_DIALOG_WINDOW_SLOTS,
            )
