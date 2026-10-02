from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.modules.blacklist.fetch import fetch_source
from app.modules.blacklist.repository import BlacklistRepository


class FetchBlacklistSourcesUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, blacklist_repository: BlacklistRepository, uow: UnitOfWork) -> None:
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        for source in await self._blacklist_repository.list_sources():
            if not source.enabled:
                continue
            try:
                parsed = await fetch_source(source.url)
            except Exception as exc:  # one bad source must not abort the rest
                logger.warning(f"Blacklist source '{source.url}' sync failed: {exc}")
                async with self._uow:
                    await self._blacklist_repository.mark_source_error(source.id, str(exc))
                continue
            async with self._uow:
                await self._blacklist_repository.replace_source_lists(source.id, parsed, error=None)
            logger.info(
                f"Blacklist source '{source.url}' synced: "
                f"{len(parsed.telegram_ids)} ids, {len(parsed.emails)} emails"
            )
