from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import AddOnDto


class ListAddOnsUseCase(UseCase[None, list[AddOnDto]]):
    required_permission = Permission.ADDONS_VIEW

    def __init__(self, addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
        self._addon_repository = addon_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[AddOnDto]:
        async with self._uow:
            return await self._addon_repository.list_all()
