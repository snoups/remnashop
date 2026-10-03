from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.events import UsersBulkUnblockedEvent
from app.modules.users.usecases.list_blacklist_matches import _ROLES, identities_of


class UnblockBlacklistMatchesUseCase(UseCase[None, int]):
    required_permission = Permission.USERS_UNBLOCK_BLACKLIST_MATCHES

    def __init__(
        self,
        user_blacklist: UserBlacklistRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_blacklist = user_blacklist
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> int:
        async with self._uow:
            origins = await self._blacklist_repository.identity_origins()
            # source-list entries can't be removed here; the next reconcile re-blocks those users
            manual_ids, manual_emails = await self._user_blacklist.matching_identities(
                *identities_of(origins, "manual"), roles=_ROLES
            )
            for telegram_id in manual_ids:
                await self._blacklist_repository.remove_entry(
                    BlacklistKind.TELEGRAM_ID, str(telegram_id)
                )
            for email in manual_emails:
                await self._blacklist_repository.remove_entry(BlacklistKind.EMAIL, email)
            count = await self._user_blacklist.unblock_matching(
                *identities_of(origins), roles=_ROLES
            )
            await self._event_publisher.publish(UsersBulkUnblockedEvent(actor=actor, count=count))

        return count
