from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import AdLinkChannel
from app.core.exceptions import ConflictError
from app.modules.advertising.repository import AdLinkRepository
from app.worker.broker import broker


async def record_ad_link_attribution(
    *,
    user_id: int,
    ad_link_code: str,
    channel: str,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
) -> None:
    ad_link = await ad_link_repository.get_by_code(ad_link_code)
    if ad_link is None or not ad_link.is_active:
        logger.debug(f"Ad link code '{ad_link_code}' not found or inactive, skipping attribution")
        return
    if not ad_link.allows(AdLinkChannel(channel)):
        logger.debug(f"Ad link '{ad_link.code}' doesn't allow channel '{channel}', skipping")
        return

    try:
        async with uow:
            await ad_link_repository.create_attribution(
                ad_link_id=ad_link.id, user_id=user_id, channel=AdLinkChannel(channel)
            )
    except ConflictError:
        # Shouldn't happen -- TelegramUserRegisteredEvent only fires once, at
        # creation -- but the UNIQUE constraint on user_id is the backstop.
        logger.debug(f"User '{user_id}' already attributed to an ad link, skipping")
        return

    logger.info(f"Attributed user '{user_id}' to ad link '{ad_link.code}'")


@broker.task
@inject(patch_module=True)
async def record_ad_link_attribution_task(
    user_id: int,
    ad_link_code: str,
    channel: str,
    ad_link_repository: FromDishka[AdLinkRepository],
    uow: FromDishka[UnitOfWork],
) -> None:
    await record_ad_link_attribution(
        user_id=user_id,
        ad_link_code=ad_link_code,
        channel=channel,
        ad_link_repository=ad_link_repository,
        uow=uow,
    )
