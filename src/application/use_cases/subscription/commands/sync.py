from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError

from src.application.common import Interactor, Remnawave
from src.application.common.dao import SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import RemnaSubscriptionDto, UserDto
from src.application.use_cases.remnawave.commands.synchronization import (
    SyncRemnaUser,
    SyncRemnaUserDto,
)
from src.application.use_cases.subscription.queries.match import (
    MatchSubscription,
    MatchSubscriptionDto,
)
from src.core.enums import SubscriptionStatus


class CheckSubscriptionSyncState(Interactor[int, bool]):
    required_permission = Permission.USER_SYNC

    def __init__(
        self,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave_sdk: RemnawaveSDK,
        match_subscription: MatchSubscription,
    ) -> None:
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave_sdk = remnawave_sdk
        self.match_subscription = match_subscription

    async def _execute(self, actor: UserDto, data: int) -> bool:
        target_user = await self.user_dao.get_by_telegram_id(data)
        if not target_user:
            raise ValueError(f"User '{data}' not found")

        bot_sub = await self.subscription_dao.get_current(data)

        try:
            remna_results = await self.remnawave_sdk.users.get_users_by_telegram_id(
                telegram_id=str(data)
            )
            remna_sub = (
                RemnaSubscriptionDto.from_remna_user(remna_results[0]) if remna_results else None
            )
        except NotFoundError:
            remna_sub = None

        if not remna_sub and not bot_sub:
            raise ValueError(f"{actor.log} No subscription data found to check for '{data}'")

        if await self.match_subscription.system(MatchSubscriptionDto(bot_sub, remna_sub)):
            logger.info(f"{actor.log} Subscription data for '{data}' is consistent")
            return False

        logger.info(f"{actor.log} Inconsistency detected for user '{data}'")
        return True


class SyncSubscriptionFromRemnawave(Interactor[int, None]):
    required_permission = Permission.USER_SYNC

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave_sdk: RemnawaveSDK,
        remnawave: Remnawave,
        sync_remna_user: SyncRemnaUser,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave_sdk = remnawave_sdk
        self.remnawave = remnawave
        self.sync_remna_user = sync_remna_user

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data)
            if not target_user:
                raise ValueError(f"User '{data}' not found")

            subscription = await self.subscription_dao.get_current(data)

            try:
                results = await self.remnawave_sdk.users.get_users_by_telegram_id(
                    telegram_id=str(data)
                )
                remna_user = results[0] if results else None
            except NotFoundError:
                remna_user = None

            if not remna_user:
                if subscription:
                    await self.subscription_dao.update_status(
                        subscription.id,  # type: ignore[arg-type]
                        SubscriptionStatus.DELETED,
                    )
                await self.user_dao.clear_current_subscription(data)
                logger.info(
                    f"{actor.log} Deleted subscription for '{data}' because it missing in Remnawave"
                )
            else:
                await self.sync_remna_user.system(SyncRemnaUserDto(remna_user, creating=False))
                logger.info(f"{actor.log} Synchronized subscription from remnapy for user '{data}'")

            await self.uow.commit()


class SyncSubscriptionFromRemnashop(Interactor[int, None]):
    required_permission = Permission.USER_SYNC

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
        sync_remna_user: SyncRemnaUser,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave
        self.sync_remna_user = sync_remna_user

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data)
            if not target_user:
                raise ValueError(f"User '{data}' not found")

            subscription = await self.subscription_dao.get_current(data)

            if not subscription:
                remna_users = await self.remnawave.get_user_by_telegram_id(target_user.telegram_id)

                if not remna_users:
                    return

                await self.remnawave.delete_user(remna_users[0].uuid)
                logger.info(
                    f"{actor.log} Deleted user '{remna_users[0].uuid}' from remnapy "
                    f"due to missing local subscription"
                )
            else:
                remna_user = await self.remnawave.get_user_by_uuid(subscription.user_remna_id)

                if remna_user:
                    await self.remnawave.update_user(
                        user=target_user,
                        uuid=subscription.user_remna_id,
                        subscription=subscription,
                    )
                    logger.info(f"{actor.log} Updated user '{data}' in Remnawave with local data")
                else:
                    created_user = await self.remnawave.create_user(
                        user=target_user,
                        subscription=subscription,
                    )
                    await self.sync_remna_user.system(
                        SyncRemnaUserDto(created_user, creating=False)
                    )
                    logger.info(f"{actor.log} Recreated user '{data}' in Remnawave with local data")

            await self.uow.commit()
