from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Optional
from uuid import UUID

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError

from src.application.common import Interactor, Remnawave
from src.application.common.dao import PlanDao, SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import PlanSnapshotDto, RemnaSubscriptionDto, SubscriptionDto, UserDto
from src.application.use_cases.remnawave import SyncRemnaUser, SyncRemnaUserDto
from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now


class ToggleSubscriptionStatus(Interactor[int, SubscriptionStatus]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        subscription_dao: SubscriptionDao,
        remnawave_sdk: RemnawaveSDK,
    ):
        self.uow = uow
        self.subscription_dao = subscription_dao
        self.remnawave_sdk = remnawave_sdk

    async def _execute(self, actor: UserDto, telegram_id: int) -> SubscriptionStatus:
        subscription = await self.subscription_dao.get_current(telegram_id)

        if not subscription:
            raise ValueError(f"Subscription for user '{telegram_id}' not found")

        is_now_active = not subscription.is_active
        new_status = SubscriptionStatus.ACTIVE if is_now_active else SubscriptionStatus.DISABLED

        async with self.uow:
            try:
                if is_now_active:
                    await self.remnawave_sdk.users.enable_user(subscription.user_remna_id)
                else:
                    await self.remnawave_sdk.users.disable_user(subscription.user_remna_id)
            except Exception as e:
                logger.error(
                    f"External API error for user '{telegram_id}' while toggling status: {e}"
                )
                raise

            await self.subscription_dao.update_status(subscription.id, new_status)  # type: ignore[arg-type]
            await self.uow.commit()

        logger.info(
            f"{actor.log} Toggled subscription status to "
            f"'{new_status.value}' for user '{telegram_id}'"
        )
        return new_status


class DeleteSubscription(Interactor[int, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave_sdk: RemnawaveSDK,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave_sdk = remnawave_sdk

    async def _execute(self, actor: UserDto, telegram_id: int) -> None:
        subscription = await self.subscription_dao.get_current(telegram_id)

        if not subscription:
            raise ValueError(f"Active subscription for user '{telegram_id}' not found")

        async with self.uow:
            try:
                await self.remnawave_sdk.users.delete_user(subscription.user_remna_id)
            except Exception as e:
                logger.error(f"Failed to delete user '{telegram_id}' from Remnawave: {e}")
                raise

            await self.user_dao.clear_current_subscription(telegram_id)
            await self.subscription_dao.update_status(subscription.id, SubscriptionStatus.DELETED)  # type: ignore[arg-type]

            await self.uow.commit()

        logger.warning(f"{actor.log} Permanently deleted subscription for user '{telegram_id}'")


@dataclass(frozen=True)
class UpdateTrafficLimitDto:
    telegram_id: int
    traffic_limit: int


class UpdateTrafficLimit(Interactor[UpdateTrafficLimitDto, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: UpdateTrafficLimitDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                raise ValueError(f"User '{data.telegram_id}' not found")

            subscription = await self.subscription_dao.get_current(data.telegram_id)
            if not subscription:
                raise ValueError(f"Subscription for '{data.telegram_id}' not found")

            subscription.traffic_limit = data.traffic_limit
            await self.subscription_dao.update(subscription)
            await self.remnawave.update_user(
                user=target_user,
                uuid=subscription.user_remna_id,
                subscription=subscription,
            )

            await self.uow.commit()

        logger.info(
            f"{actor.log} Changed traffic limit to '{data.traffic_limit}' for '{data.telegram_id}'"
        )


@dataclass(frozen=True)
class UpdateDeviceLimitDto:
    telegram_id: int
    device_limit: int


class UpdateDeviceLimit(Interactor[UpdateDeviceLimitDto, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: UpdateDeviceLimitDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                raise ValueError(f"User '{data.telegram_id}' not found")

            subscription = await self.subscription_dao.get_current(data.telegram_id)
            if not subscription:
                raise ValueError(f"Subscription for '{data.telegram_id}' not found")

            subscription.device_limit = data.device_limit
            await self.subscription_dao.update(subscription)
            await self.remnawave.update_user(
                user=target_user,
                uuid=subscription.user_remna_id,
                subscription=subscription,
            )
            await self.uow.commit()

        logger.info(
            f"{actor.log} Changed device limit to '{data.device_limit}' for '{data.telegram_id}'"
        )


@dataclass(frozen=True)
class ToggleInternalSquadDto:
    telegram_id: int
    squad_id: UUID


class ToggleInternalSquad(Interactor[ToggleInternalSquadDto, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: ToggleInternalSquadDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            subscription = await self.subscription_dao.get_current(data.telegram_id)
            if not target_user or not subscription:
                raise ValueError(f"Data for user '{data.telegram_id}' not found")

            squads = list(subscription.internal_squads)
            if data.squad_id in squads:
                squads.remove(data.squad_id)
                action = "Unset"
            else:
                squads.append(data.squad_id)
                action = "Set"

            subscription.internal_squads = squads
            await self.subscription_dao.update(subscription)
            await self.remnawave.update_user(
                user=target_user,
                uuid=subscription.user_remna_id,
                subscription=subscription,
            )
            await self.uow.commit()

        logger.info(
            f"{actor.log} {action} internal squad '{data.squad_id}' for '{data.telegram_id}'"
        )


@dataclass(frozen=True)
class ToggleExternalSquadDto:
    target_telegram_id: int
    squad_id: UUID


class ToggleExternalSquad(Interactor[ToggleExternalSquadDto, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: ToggleExternalSquadDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.target_telegram_id)
            subscription = await self.subscription_dao.get_current(data.target_telegram_id)

            if not target_user or not subscription:
                raise ValueError(f"Data for user '{data.target_telegram_id}' not found")

            if data.squad_id == subscription.external_squad:
                new_squad = None
                action = "Unset"
            else:
                new_squad = data.squad_id
                action = "Set"

            subscription.external_squad = new_squad
            await self.subscription_dao.update(subscription)
            await self.remnawave.update_user(
                user=target_user,
                uuid=subscription.user_remna_id,
                subscription=subscription,
            )
            await self.uow.commit()

        logger.info(
            f"{actor.log} {action} external squad '{data.squad_id}' for '{data.target_telegram_id}'"
        )


@dataclass(frozen=True)
class AddSubscriptionDurationDto:
    telegram_id: int
    days: int


class AddSubscriptionDuration(Interactor[AddSubscriptionDurationDto, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: AddSubscriptionDurationDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            subscription = await self.subscription_dao.get_current(data.telegram_id)

            if not target_user or not subscription:
                raise ValueError(f"Subscription data for '{data.telegram_id}' not found")

            new_expire = subscription.expire_at + timedelta(days=data.days)

            if new_expire < datetime_now():
                raise ValueError(f"{actor.log} Invalid expire time for '{data.telegram_id}'")

            subscription.expire_at = new_expire
            await self.subscription_dao.update(subscription)

            subscription.expire_at = new_expire
            await self.remnawave.update_user(
                user=target_user,
                uuid=subscription.user_remna_id,
                subscription=subscription,
            )

            await self.uow.commit()

        logger.info(
            f"{actor.log} {'Added' if data.days > 0 else 'Subtracted'} '{abs(data.days)}' "
            f"days to subscription for '{data.telegram_id}'"
        )


@dataclass(frozen=True)
class MatchSubscriptionDto:
    bot_subscription: Optional[SubscriptionDto]
    remna_subscription: Optional[RemnaSubscriptionDto]


class MatchSubscription(Interactor[MatchSubscriptionDto, bool]):
    required_permission = None

    async def _execute(self, actor: UserDto, data: MatchSubscriptionDto) -> bool:
        bot_sub = data.bot_subscription
        remna_sub = data.remna_subscription

        if not bot_sub or not remna_sub:
            return False

        is_match = (
            bot_sub.user_remna_id == remna_sub.uuid
            and bot_sub.status == remna_sub.status
            and bot_sub.url == remna_sub.url
            and bot_sub.traffic_limit == remna_sub.traffic_limit
            and bot_sub.device_limit == remna_sub.device_limit
            and bot_sub.expire_at == remna_sub.expire_at
            and bot_sub.external_squad == remna_sub.external_squad
            and bot_sub.traffic_limit_strategy == remna_sub.traffic_limit_strategy
            and bot_sub.tag == remna_sub.tag
            and sorted(bot_sub.internal_squads) == sorted(remna_sub.internal_squads)
        )

        if not is_match:
            logger.info(f"{actor.log} Subscription data mismatch for user")

        return is_match


class CheckSubscriptionSyncState(Interactor[int, bool]):
    required_permission = Permission.USER_SYNC

    def __init__(
        self,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: RemnawaveSDK,
        match_subscription: MatchSubscription,
    ):
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave
        self.match_subscription = match_subscription

    async def _execute(self, actor: UserDto, data: int) -> bool:
        target_user = await self.user_dao.get_by_telegram_id(data)
        if not target_user:
            raise ValueError(f"User '{data}' not found")

        bot_sub = await self.subscription_dao.get_current(data)

        try:
            remna_results = await self.remnawave.users.get_users_by_telegram_id(
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
    ):
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
                logger.info(
                    f"{actor.log} Synchronized subscription from Remnawave for user '{data}'"
                )

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
    ):
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
                    f"{actor.log} Deleted user '{remna_users[0].uuid}' from Remnawave "
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


@dataclass(frozen=True)
class SetUserSubscriptionDto:
    telegram_id: int
    plan_id: int
    duration: int


class SetUserSubscription(Interactor[SetUserSubscriptionDto, None]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        plan_dao: PlanDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.uow = uow
        self.user_dao = user_dao
        self.plan_dao = plan_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: SetUserSubscriptionDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                raise ValueError(f"User '{data.telegram_id}' not found")

            plan = await self.plan_dao.get_by_id(data.plan_id)
            if not plan:
                raise ValueError(f"Plan '{data.plan_id}' not found")

            plan_snapshot = PlanSnapshotDto.from_plan(plan, data.duration)
            subscription = await self.subscription_dao.get_current(data.telegram_id)

            if subscription:
                remna_user = await self.remnawave.update_user(
                    user=target_user,
                    uuid=subscription.user_remna_id,
                    plan=plan_snapshot,
                    reset_traffic=True,
                )
            else:
                remna_user = await self.remnawave.create_user(user=target_user, plan=plan_snapshot)

            new_subscription = SubscriptionDto(
                user_remna_id=remna_user.uuid,
                status=SubscriptionStatus(remna_user.status),
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                traffic_limit_strategy=plan.traffic_limit_strategy,
                tag=plan.tag,
                internal_squads=plan.internal_squads,
                external_squad=plan.external_squad,
                expire_at=remna_user.expire_at,
                url=remna_user.subscription_url,
                plan_snapshot=plan_snapshot,
            )

            new_subscription = await self.subscription_dao.create(
                new_subscription,
                data.telegram_id,
            )
            await self.uow.commit()

        logger.info(
            f"{actor.log} Set subscription with plan '{data.plan_id}' duration "
            f"'{data.duration}' for '{data.telegram_id}'"
        )


SUBSCRIPTION_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    ToggleSubscriptionStatus,
    DeleteSubscription,
    UpdateTrafficLimit,
    UpdateDeviceLimit,
    ToggleInternalSquad,
    ToggleExternalSquad,
    AddSubscriptionDuration,
    MatchSubscription,
    CheckSubscriptionSyncState,
    SyncSubscriptionFromRemnawave,
    SyncSubscriptionFromRemnashop,
    SetUserSubscription,
)
