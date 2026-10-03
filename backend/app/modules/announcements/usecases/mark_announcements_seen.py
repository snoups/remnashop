from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.users import UserDto


class MarkAnnouncementsSeenUseCase(UseCase[list[str], None, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, announcement_repository: AnnouncementRepository, uow: UnitOfWork) -> None:
        self._announcement_repository = announcement_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: list[str]) -> None:
        async with self._uow:
            await self._announcement_repository.mark_seen(
                actor.id, sorted(set(data)), datetime_now()
            )
