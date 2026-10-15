from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistReconciledEvent, BlacklistRepository
from app.modules.users.blacklist_repository import UserBlacklistRepository


class BlockBlacklistMatchesUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        blacklist_repository: BlacklistRepository,
        user_blacklist: UserBlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._blacklist_repository = blacklist_repository
        self._user_blacklist = user_blacklist
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            ids, emails = await self._blacklist_repository.all_blocked_identities()
            if not ids and not emails:
                return
            blocked = await self._user_blacklist.block_matching(ids, emails)
            if blocked:
                await self._event_publisher.publish(
                    BlacklistReconciledEvent(blocked_user_ids=blocked)
                )
        if blocked:
            logger.warning(f"Blacklist reconcile blocked {len(blocked)} user(s)")
