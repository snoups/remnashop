from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.utils.lock import cron_lock
from app.modules.blacklist.events import BlacklistReconciledEvent
from app.modules.blacklist.fetch import fetch_source
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.users import UserRepository
from app.worker.broker import broker

_SYNC_LOCK_TTL_S: Final[int] = 55 * 60
_RECONCILE_LOCK_TTL_S: Final[int] = 10 * 60


async def sync_blacklist_sources(
    blacklist_repository: BlacklistRepository, uow: UnitOfWork
) -> None:
    for source in await blacklist_repository.list_sources():
        if not source.enabled:
            continue
        try:
            parsed = await fetch_source(source.url)
        except Exception as exc:  # noqa: BLE001 -- one bad source must not abort the rest
            logger.warning(f"Blacklist source '{source.url}' sync failed: {exc}")
            async with uow:
                await blacklist_repository.mark_source_error(source.id, str(exc))
            continue
        async with uow:
            await blacklist_repository.replace_source_lists(source.id, parsed, error=None)
        logger.info(
            f"Blacklist source '{source.url}' synced: "
            f"{len(parsed.telegram_ids)} ids, {len(parsed.emails)} emails"
        )


async def reconcile_blacklist(
    blacklist_repository: BlacklistRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    ids, emails = await blacklist_repository.all_blocked_identities()
    if not ids and not emails:
        return
    async with uow:
        blocked = await user_repository.block_matching(ids, emails)
        if blocked:
            await event_publisher.publish(BlacklistReconciledEvent(blocked_user_ids=blocked))
    if blocked:
        logger.warning(f"Blacklist reconcile blocked {len(blocked)} user(s)")


@broker.task(schedule=[{"cron": "0 */6 * * *"}])
@inject(patch_module=True)
async def sync_blacklist_sources_task(
    blacklist_repository: FromDishka[BlacklistRepository],
    uow: FromDishka[UnitOfWork],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(redis, "blacklist_sync", ttl_seconds=_SYNC_LOCK_TTL_S) as acquired:
        if not acquired:
            return
        await sync_blacklist_sources(blacklist_repository, uow)
    await reconcile_blacklist_task.kiq()  # type: ignore[call-overload]


@broker.task(schedule=[{"cron": "0 * * * *"}])
@inject(patch_module=True)
async def reconcile_blacklist_task(
    blacklist_repository: FromDishka[BlacklistRepository],
    user_repository: FromDishka[UserRepository],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
    redis: FromDishka[Redis],
) -> None:
    async with cron_lock(
        redis, "blacklist_reconcile", ttl_seconds=_RECONCILE_LOCK_TTL_S
    ) as acquired:
        if not acquired:
            return
        await reconcile_blacklist(blacklist_repository, user_repository, uow, event_publisher)
