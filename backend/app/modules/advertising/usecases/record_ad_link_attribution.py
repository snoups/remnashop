from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.exceptions import ConflictError
from app.core.usecase import UseCase
from app.modules.advertising.dto import RecordAdLinkAttributionDto
from app.modules.advertising.repository import AdLinkRepository


class RecordAdLinkAttributionUseCase(UseCase[RecordAdLinkAttributionDto, None]):
    required_permission = None

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: RecordAdLinkAttributionDto) -> None:
        ad_link = await self._ad_link_repository.get_by_code(data.ad_link_code)
        if ad_link is None or not ad_link.is_active:
            logger.debug(
                f"Ad link code '{data.ad_link_code}' not found or inactive, skipping attribution"
            )
            return
        if not ad_link.allows(data.channel):
            logger.debug(f"Ad link '{ad_link.code}' doesn't allow channel '{data.channel}'")
            return

        try:
            async with self._uow:
                await self._ad_link_repository.create_attribution(
                    ad_link_id=ad_link.id, user_id=data.user_id, channel=data.channel
                )
        except ConflictError:
            # Shouldn't happen -- TelegramUserRegisteredEvent only fires once, at
            # creation -- but the UNIQUE constraint on user_id is the backstop.
            logger.debug(f"User '{data.user_id}' already attributed to an ad link, skipping")
            return

        logger.info(f"Attributed user '{data.user_id}' to ad link '{ad_link.code}'")
