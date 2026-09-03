from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import BulkBlockResultDto, UserDto
from app.modules.users.events import UsersBulkBlockedEvent
from app.modules.users.repository import UserRepository


class BulkBlockUsersUseCase(UseCase[list[int], BulkBlockResultDto]):
    required_permission = Permission.USERS_BULK_BLOCK

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, telegram_ids: list[int]) -> BulkBlockResultDto:
        known_ids: list[int] = []
        unknown_ids: list[int] = []
        skipped = 0
        for telegram_id in telegram_ids:
            target = await self._user_repository.get_by_telegram_id(telegram_id)
            if target is None:
                unknown_ids.append(telegram_id)
            elif actor.role > target.role:
                known_ids.append(telegram_id)
            else:
                skipped += 1

        async with self._uow:
            blocked_user_ids = await self._user_repository.bulk_block_by_telegram_ids(known_ids)
            added_to_list = 0
            for telegram_id in unknown_ids:
                added = await self._blacklist_repository.add_entry(
                    BlacklistKind.TELEGRAM_ID, str(telegram_id)
                )
                if added:
                    added_to_list += 1
            await self._event_publisher.publish(
                UsersBulkBlockedEvent(actor=actor, count=len(blocked_user_ids))
            )

        return BulkBlockResultDto(
            blocked=len(blocked_user_ids), added_to_list=added_to_list, skipped=skipped
        )
