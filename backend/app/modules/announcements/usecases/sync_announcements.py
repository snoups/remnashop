import httpx
from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.modules.announcements.feed import FeedError, parse_feed
from app.modules.announcements.fetch import fetch_feed
from app.modules.announcements.repository import AnnouncementRepository


class SyncAnnouncementsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, announcement_repository: AnnouncementRepository, uow: UnitOfWork) -> None:
        self._announcement_repository = announcement_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        try:
            items = parse_feed(await fetch_feed())
        except (httpx.HTTPError, FeedError) as error:
            # an unreachable or broken feed must not wipe what admins already have
            logger.warning(f"Announcements feed sync failed, keeping the current set: {error}")
            return
        async with self._uow:
            await self._announcement_repository.replace_all(items)
        logger.info(f"Announcements feed synced: {len(items)} items")
