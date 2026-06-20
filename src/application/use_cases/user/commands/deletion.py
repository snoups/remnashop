from loguru import logger

from src.application.common import Interactor, Remnawave
from src.application.common.dao import SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDeletionSummaryDto, UserDto


class DeleteUserCompletely(Interactor[int, UserDeletionSummaryDto]):
    required_permission = Permission.USER_DELETE

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(
        self,
        actor: UserDto,
        telegram_id: int,
    ) -> UserDeletionSummaryDto:
        target = await self.user_dao.get_by_telegram_id(telegram_id)
        if not target:
            raise ValueError(f"User '{telegram_id}' not found")
        if actor.telegram_id == telegram_id:
            raise PermissionError("Administrators cannot delete themselves")
        if actor.role <= target.role:
            raise PermissionError("Cannot delete user with equal or higher role")

        subscriptions = await self.subscription_dao.get_all_by_user(telegram_id)
        remna_ids = {subscription.user_remna_id for subscription in subscriptions}
        logger.warning(
            f"{actor.log} Started complete deletion of user '{telegram_id}'; "
            f"local_subscriptions='{len(subscriptions)}', remnawave_users='{len(remna_ids)}'"
        )

        deleted_remna_users = 0
        for remna_id in remna_ids:
            if await self.remnawave.delete_user(remna_id):
                deleted_remna_users += 1

        try:
            async with self.uow:
                summary = await self.user_dao.delete_user_completely(telegram_id)
                await self.uow.commit()
        except Exception:
            logger.exception(
                f"{actor.log} Local deletion failed for user '{telegram_id}' after "
                f"Remnawave cleanup; retry is safe"
            )
            raise

        logger.warning(
            f"{actor.log} Completely deleted user '{telegram_id}'; "
            f"remnawave_deleted='{deleted_remna_users}', summary='{summary}'"
        )
        return summary
