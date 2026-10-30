from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.customer_notifications.dto import FEED_RETENTION
from app.modules.customer_notifications.repository import CustomerNotificationRepository


class PruneCustomerNotificationsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(self, repository: CustomerNotificationRepository, uow: UnitOfWork) -> None:
        self._repository = repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            deleted = await self._repository.delete_older_than(datetime_now() - FEED_RETENTION)
        logger.info(f"Pruned {deleted} customer_notifications row(s)")
