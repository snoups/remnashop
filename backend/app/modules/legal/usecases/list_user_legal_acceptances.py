from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.legal.dto import LegalAcceptanceDto
from app.modules.legal.repository import LegalRepository
from app.modules.users import UserRepository, get_visible_target


class ListUserLegalAcceptancesUseCase(UseCase[int, list[LegalAcceptanceDto]]):
    required_permission = Permission.LEGAL_ACCEPTANCES_VIEW

    def __init__(
        self,
        legal_repository: LegalRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> list[LegalAcceptanceDto]:
        async with self._uow:
            user = await get_visible_target(self._user_repository, actor, data)
            return await self._legal_repository.list_acceptances(user.id)
