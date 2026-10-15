from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import DialogWindowDto
from app.modules.dialogs.repository import DialogRepository


class ListDialogWindowsUseCase(UseCase[None, list[DialogWindowDto]]):
    required_permission = Permission.DIALOGS_WINDOWS_VIEW

    def __init__(self, dialog_repository: DialogRepository, uow: UnitOfWork) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[DialogWindowDto]:
        async with self._uow:
            return await self._dialog_repository.list_all()
