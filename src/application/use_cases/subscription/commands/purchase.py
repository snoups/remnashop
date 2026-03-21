from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from loguru import logger

from src.application.common import EventPublisher, Interactor, Redirect, Remnawave, TranslatorRunner
from src.application.common.dao import SubscriptionDao, TransactionDao, UserDao
from src.application.common.uow import UnitOfWork
from src.application.dto import PlanSnapshotDto, SubscriptionDto, TransactionDto, UserDto
from src.application.events import TrialActivatedEvent
from src.core.enums import PurchaseType, SubscriptionStatus, TransactionStatus
from src.core.exceptions import PurchaseError, TrialError
from src.core.types import RemnaUserDto
from src.core.utils.converters import days_to_datetime
from src.core.utils.i18n_helpers import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.time import datetime_now


@dataclass(frozen=True)
class ActivateTrialSubscriptionDto:
    user: UserDto
    plan: PlanSnapshotDto


class ActivateTrialSubscription(Interactor[ActivateTrialSubscriptionDto, None]):
    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
        event_publisher: EventPublisher,
        redirect: Redirect,
        i18n: TranslatorRunner,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave
        self.event_publisher = event_publisher
        self.redirect = redirect
        self.i18n = i18n

    async def _execute(self, actor: UserDto, data: ActivateTrialSubscriptionDto) -> None:
        user = data.user
        plan = data.plan

        logger.info(f"{actor.log} Started trial for user '{user.telegram_id}'")

        try:
            created_user = await self.remnawave.create_user(user, plan=plan)

            trial_subscription = SubscriptionDto(
                user_remna_id=created_user.uuid,
                status=SubscriptionStatus(created_user.status),
                is_trial=True,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                traffic_limit_strategy=plan.traffic_limit_strategy,
                tag=plan.tag,
                internal_squads=plan.internal_squads,
                external_squad=plan.external_squad,
                expire_at=created_user.expire_at,
                url=created_user.subscription_url,
                plan_snapshot=plan,
            )

            async with self.uow:
                await self.subscription_dao.create(
                    subscription=trial_subscription,
                    telegram_id=user.telegram_id,
                )
                await self.user_dao.set_trial_available(user.telegram_id, False)
                await self.uow.commit()

            logger.debug(
                f"{actor.log} Created new trial subscription for user '{user.telegram_id}'"
            )

            event = TrialActivatedEvent(
                telegram_id=user.telegram_id,
                username=user.username,
                name=user.name,
                plan_name=self.i18n.get(plan.name),
                plan_type=plan.type,
                plan_traffic_limit=i18n_format_traffic_limit(plan.traffic_limit),
                plan_device_limit=i18n_format_device_limit(plan.device_limit),
                plan_duration=i18n_format_days(plan.duration),
            )
            await self.event_publisher.publish(event)
            await self.redirect.to_success_trial(user.telegram_id)
            logger.info(
                f"{actor.log} Trial subscription completed "
                f"successfully for user '{user.telegram_id}'"
            )

        except Exception as e:
            logger.exception(f"{actor.log} Failed to give trial for user '{user.telegram_id}'")
            await self.redirect.to_failed_payment(user.telegram_id)
            raise TrialError(e)


@dataclass(frozen=True)
class PurchaseSubscriptionDto:
    user: UserDto
    transaction: TransactionDto
    subscription: Optional[SubscriptionDto]


class PurchaseSubscription(Interactor[PurchaseSubscriptionDto, None]):
    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        transaction_dao: TransactionDao,
        remnawave: Remnawave,
        redirect: Redirect,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.transaction_dao = transaction_dao
        self.remnawave = remnawave
        self.redirect = redirect

    async def _execute(self, actor: UserDto, data: PurchaseSubscriptionDto) -> None:
        user = data.user
        transaction = data.transaction
        subscription = data.subscription
        plan = transaction.plan_snapshot
        purchase_type = transaction.purchase_type
        has_trial = subscription.is_trial if subscription else False

        if not user or not plan:
            logger.error(f"{actor.log} User or plan not found for transaction '{transaction.id}'")
            return

        logger.info(
            f"{actor.log} Purchase subscription started: '{purchase_type}' "
            f"for user '{user.telegram_id}'"
        )

        async with self.uow:
            try:
                # 1. NEW PURCHASE (NOT TRIAL)
                if purchase_type == PurchaseType.NEW and not has_trial:
                    created_user = await self.remnawave.create_user(user, plan=plan)
                    new_sub = self._build_subscription_dto(created_user, plan)

                    await self.subscription_dao.create(
                        subscription=new_sub,
                        telegram_id=user.telegram_id,
                    )
                    await self.user_dao.set_trial_available(user.telegram_id, False)
                    await self.uow.commit()

                    logger.debug(
                        f"{actor.log} Created new subscription for user '{user.telegram_id}'"
                    )

                # 2. RENEW (NOT TRIAL)
                elif purchase_type == PurchaseType.RENEW and not has_trial:
                    if not subscription:
                        raise ValueError(
                            f"No subscription found for renewal for user '{user.telegram_id}'"
                        )

                    base_date = max(subscription.expire_at, datetime_now())
                    duration = transaction.plan_snapshot.duration

                    if duration == 0:
                        new_expire = days_to_datetime(duration)  # unlimited
                    else:
                        base_date = max(subscription.expire_at, datetime_now())
                        new_expire = base_date + timedelta(days=duration)

                    subscription.expire_at = new_expire

                    updated_user = await self.remnawave.update_user(
                        user=user,
                        uuid=subscription.user_remna_id,
                        subscription=subscription,
                        reset_traffic=True,
                    )

                    subscription.plan_snapshot = plan
                    await self.subscription_dao.update(subscription)
                    await self.uow.commit()
                    logger.debug(f"{actor.log} Renewed subscription for user '{user.telegram_id}'")

                # 3. CHANGE OR CONVERT FROM TRIAL
                elif purchase_type == PurchaseType.CHANGE or has_trial:
                    if not subscription:
                        raise ValueError(
                            f"No subscription found for change for user '{user.telegram_id}'"
                        )

                    # Deactivate old subscription
                    await self.subscription_dao.update_status(
                        subscription_id=subscription.id,  # type: ignore[arg-type]
                        status=SubscriptionStatus.DISABLED,
                    )

                    updated_user = await self.remnawave.update_user(
                        user=user,
                        uuid=subscription.user_remna_id,
                        plan=plan,
                        reset_traffic=True,
                    )

                    new_sub = self._build_subscription_dto(updated_user, plan)
                    await self.subscription_dao.create(
                        subscription=new_sub,
                        telegram_id=user.telegram_id,
                    )

                    await self.uow.commit()
                    logger.debug(f"{actor.log} Changed subscription for user '{user.telegram_id}'")

                else:
                    raise ValueError(
                        f"Unknown purchase type '{purchase_type}' for user '{user.telegram_id}'"
                    )

                await self.redirect.to_success_payment(user.telegram_id, purchase_type)
                logger.info(
                    f"{actor.log} Purchase subscription completed for user '{user.telegram_id}'"
                )

            except Exception as e:
                logger.exception(
                    f"{actor.log} Failed to process purchase type '{purchase_type}' "
                    f"for user '{user.telegram_id}'"
                )

                await self.transaction_dao.update_status(
                    transaction.payment_id,
                    TransactionStatus.FAILED,
                )
                await self.uow.commit()

                await self.redirect.to_failed_payment(user.telegram_id)
                raise PurchaseError(e)

    def _build_subscription_dto(
        self,
        remna_user: RemnaUserDto,
        plan: PlanSnapshotDto,
    ) -> SubscriptionDto:
        return SubscriptionDto(
            user_remna_id=remna_user.uuid,
            status=SubscriptionStatus(remna_user.status),
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            traffic_limit_strategy=plan.traffic_limit_strategy,
            tag=plan.tag,
            internal_squads=plan.internal_squads,
            external_squad=plan.external_squad,
            expire_at=remna_user.expire_at,
            url=remna_user.subscription_url,  # type: ignore[arg-type]
            plan_snapshot=plan,
        )
