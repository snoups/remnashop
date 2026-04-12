from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from loguru import logger
from remnapy import RemnawaveSDK

from src.application.common import Interactor, Remnawave
from src.application.common.dao import SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto
from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now


class ToggleSubscriptionStatus(Interactor[int, SubscriptionStatus]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        subscription_dao: SubscriptionDao,
        remnawave_sdk: RemnawaveSDK,
    ) -> None:
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
    ) -> None:
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
                logger.error(f"Failed to delete user '{telegram_id}' from remnapy: {e}")
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
    ) -> None:
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
    ) -> None:
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
    ) -> None:
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
    ) -> None:
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
    ) -> None:
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
