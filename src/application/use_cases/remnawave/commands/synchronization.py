from dataclasses import dataclass

from loguru import logger

from src.application.common import Cryptographer, Interactor, Remnawave
from src.application.common.dao import SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import PlanSnapshotDto, RemnaSubscriptionDto, SubscriptionDto, UserDto
from src.core.config import AppConfig
from src.core.constants import IMPORTED_TAG
from src.core.enums import Role, SubscriptionStatus
from src.core.types import RemnaUserDto
from src.core.utils.converters import limits_to_plan_type
from src.core.utils.time import datetime_now


@dataclass(frozen=True)
class SyncRemnaUserDto:
    remna_user: RemnaUserDto
    creating: bool


class SyncRemnaUser(Interactor[SyncRemnaUserDto, bool]):
    required_permission = Permission.USER_SYNC

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        config: AppConfig,
        remnawave: Remnawave,
        cryptographer: Cryptographer,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.config = config
        self.remnawave = remnawave
        self.cryptographer = cryptographer

    async def _execute(self, actor: UserDto, data: SyncRemnaUserDto) -> bool:
        remna_user = data.remna_user

        if not remna_user.telegram_id:
            logger.warning(f"Skipping sync for '{remna_user.username}': missing 'telegram_id'")
            return False

        async with self.uow:
            user = await self.user_dao.get_by_telegram_id(int(remna_user.telegram_id))

            if not user and data.creating:
                logger.debug(f"User '{remna_user.telegram_id}' not found in bot, creating new user")
                user = await self.user_dao.create(self._create_user_dto(data.remna_user))

            if not user:
                logger.warning(
                    f"Sync failed: user '{remna_user.telegram_id}' could not be found or created"
                )
                return False

            subscription = await self.subscription_dao.get_current(user.telegram_id)
            remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_user)

            if not subscription:
                logger.info(
                    f"No subscription found for user '{user.telegram_id}', importing from panel"
                )
                await self._import_subscription(user.telegram_id, remna_subscription)
                await self.uow.commit()
                logger.info(f"Sync completed for user '{remna_user.telegram_id}'")
                return False
            else:
                logger.info(f"Synchronizing existing subscription for user '{user.telegram_id}'")
                changed = await self._update_subscription(subscription, remna_subscription)
                await self.uow.commit()
                logger.info(f"Sync completed for user '{remna_user.telegram_id}'")
                return changed

    def _create_user_dto(self, data: RemnaUserDto) -> UserDto:
        return UserDto(
            telegram_id=data.telegram_id,  # type: ignore[arg-type]
            referral_code=self.cryptographer.generate_short_code(data.telegram_id),
            name=str(data.telegram_id),
            role=Role.USER,
            language=self.config.default_locale,
        )

    async def _import_subscription(
        self,
        telegram_id: int,
        remna_subscription: RemnaSubscriptionDto,
    ) -> None:
        plan = PlanSnapshotDto(
            id=-1,
            name=IMPORTED_TAG,
            tag=remna_subscription.tag,
            type=limits_to_plan_type(
                remna_subscription.traffic_limit,
                remna_subscription.device_limit,
            ),
            traffic_limit=remna_subscription.traffic_limit,
            device_limit=remna_subscription.device_limit,
            duration=0,
            traffic_limit_strategy=remna_subscription.traffic_limit_strategy,
            internal_squads=remna_subscription.internal_squads,
            external_squad=remna_subscription.external_squad,
        )

        expired = remna_subscription.expire_at and remna_subscription.expire_at < datetime_now()
        status = (
            SubscriptionStatus.EXPIRED if expired else SubscriptionStatus(remna_subscription.status)
        )

        subscription = SubscriptionDto(
            user_remna_id=remna_subscription.uuid,
            status=status,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            traffic_limit_strategy=plan.traffic_limit_strategy,
            tag=plan.tag,
            internal_squads=remna_subscription.internal_squads,
            external_squad=remna_subscription.external_squad,
            expire_at=remna_subscription.expire_at,
            url=remna_subscription.url,
            plan_snapshot=plan,
        )

        subscription = await self.subscription_dao.create(subscription, telegram_id)

    async def _update_subscription(
        self,
        target: SubscriptionDto,
        source: RemnaSubscriptionDto,
    ) -> bool:
        subscription = self.remnawave.apply_sync(target, source)
        await self.subscription_dao.update(subscription)
        return bool(subscription.changed_data)
