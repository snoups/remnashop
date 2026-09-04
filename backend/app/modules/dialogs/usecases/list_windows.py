from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import DialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.users import UserDto


class ListDialogWindowsUseCase(UseCase[None, list[DialogWindowDto]]):
    required_permission = Permission.DIALOGS_WINDOWS_VIEW

    def __init__(self, dialog_repository: DialogRepository) -> None:
        self._dialog_repository = dialog_repository

    async def _execute(self, actor: UserDto, data: None) -> list[DialogWindowDto]:
        return await self._dialog_repository.list_all()
