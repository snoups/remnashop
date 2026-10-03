from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.announcements.dto import AnnouncementDto
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.announcements.visibility import is_visible, parse_panel_version
from app.modules.users import UserDto


class ListAnnouncementsUseCase(UseCase[None, list[AnnouncementDto], UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        announcement_repository: AnnouncementRepository,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._announcement_repository = announcement_repository
        self._uow = uow
        self._config = config

    async def _execute(self, actor: UserDto, data: None) -> list[AnnouncementDto]:
        now = datetime_now()
        panel_version = parse_panel_version(self._config.build.version)
        async with self._uow:
            rows = await self._announcement_repository.list_for_user(
                actor.id,
                # a new admin doesn't inherit years of history
                notify_from=actor.created_at or now,
                now=now,
            )
        return [
            row
            for row in rows
            if is_visible(row, role=actor.role, panel_version=panel_version, now=now)
        ]
