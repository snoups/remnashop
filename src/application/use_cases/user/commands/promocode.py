from dataclasses import dataclass
from datetime import timedelta

from loguru import logger

from src.application.common import EventPublisher, Interactor, Remnawave
from src.application.common.dao import PromocodeDao, SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import (
    ActivatePromocodeResultDto,
    PromocodeActivationDto,
    PromocodeDto,
    SubscriptionDto,
    UserDto,
)
from src.application.events import PromocodeActivatedEvent
from src.application.use_cases.promocode.utils import get_promocode_runtime_state
from src.core.enums import PromocodeRewardType
from src.core.exceptions import PromocodeError
from src.core.utils.time import datetime_now


@dataclass(frozen=True)
class ActivatePromocodeDto:
    code: str


class ActivatePromocode(Interactor[ActivatePromocodeDto, ActivatePromocodeResultDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        promocode_dao: PromocodeDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
        event_publisher: EventPublisher,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.promocode_dao = promocode_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave
        self.event_publisher = event_publisher

    async def _execute(
        self,
        actor: UserDto,
        data: ActivatePromocodeDto,
    ) -> ActivatePromocodeResultDto:
        normalized_code = data.code.strip().upper()
        if not normalized_code:
            raise PromocodeError("ntf-promocode.empty", "Promocode is empty")

        async with self.uow:
            user = await self.user_dao.get_by_telegram_id(actor.telegram_id)
            if not user:
                raise ValueError(f"User '{actor.telegram_id}' not found")

            promocode = await self.promocode_dao.get_by_code(normalized_code)
            if not promocode or not promocode.is_active:
                raise PromocodeError(
                    "ntf-promocode.not-found",
                    f"Promocode '{normalized_code}' not found or disabled",
                )

            if promocode.id is None:
                raise ValueError(f"Promocode '{normalized_code}' has no database id")

            if await self.promocode_dao.is_activated_by_user(promocode.id, user.telegram_id):
                raise PromocodeError(
                    "ntf-promocode.already-activated",
                    f"Promocode '{normalized_code}' already activated by user '{user.telegram_id}'",
                )

            activations = await self.promocode_dao.count_activations(promocode.id)
            runtime_state = get_promocode_runtime_state(promocode, activations)

            if runtime_state.is_expired:
                await self._disable_promocode(promocode)
                raise PromocodeError(
                    "ntf-promocode.expired",
                    f"Promocode '{normalized_code}' is expired",
                )

            if runtime_state.is_limit_reached:
                await self._disable_promocode(promocode)
                raise PromocodeError(
                    "ntf-promocode.limit-reached",
                    f"Promocode '{normalized_code}' reached activation limit",
                )

            applied_discount = await self._apply_reward(user, promocode)
            updated_user = user
            if user.changed_data:
                updated_user = await self.user_dao.update(user) or user

            await self.promocode_dao.create_activation(
                PromocodeActivationDto(
                    promocode_id=promocode.id,
                    user_telegram_id=updated_user.telegram_id,
                )
            )

            final_runtime_state = get_promocode_runtime_state(promocode, activations + 1)
            if final_runtime_state.should_disable:
                await self._disable_promocode(promocode, commit=False)

            await self.uow.commit()

        await self.event_publisher.publish(
            PromocodeActivatedEvent(
                telegram_id=updated_user.telegram_id,
                username=updated_user.username,
                name=updated_user.name,
                code=promocode.code,
                promocode_type=promocode.reward_type,
                reward=promocode.reward or applied_discount,
                applied_discount=applied_discount,
                has_activation_limit=final_runtime_state.has_activation_limit,
                remaining_activations=final_runtime_state.remaining_activations,
                has_lifetime_limit=final_runtime_state.has_lifetime_limit,
                remaining_lifetime_days=final_runtime_state.remaining_lifetime_days,
            )
        )

        logger.info(
            f"{updated_user.log} Activated promocode '{promocode.code}' "
            f"with type '{promocode.reward_type}' and reward '{promocode.reward}'"
        )

        return ActivatePromocodeResultDto(
            user=updated_user,
            code=promocode.code,
            promocode_type=promocode.reward_type,
            reward=promocode.reward or applied_discount,
            applied_discount=applied_discount,
            has_activation_limit=final_runtime_state.has_activation_limit,
            remaining_activations=final_runtime_state.remaining_activations,
            has_lifetime_limit=final_runtime_state.has_lifetime_limit,
            remaining_lifetime_days=final_runtime_state.remaining_lifetime_days,
        )

    async def _apply_reward(self, user: UserDto, promocode: PromocodeDto) -> int:
        reward = promocode.reward
        if reward is None or reward <= 0:
            raise PromocodeError(
                "ntf-promocode.invalid-reward",
                f"Promocode '{promocode.code}' has invalid reward '{reward}'",
            )

        applied_discount = min(reward, 100)

        match promocode.reward_type:
            case PromocodeRewardType.PURCHASE_DISCOUNT:
                applied_discount = max(user.purchase_discount, applied_discount)
                user.purchase_discount = applied_discount
            case PromocodeRewardType.PERSONAL_DISCOUNT:
                applied_discount = max(user.personal_discount, applied_discount)
                user.personal_discount = applied_discount
            case PromocodeRewardType.DURATION:
                applied_discount = 0
                subscription = await self._require_subscription(user.telegram_id, promocode)

                if subscription.expire_at.year == 2099:
                    raise PromocodeError(
                        "ntf-promocode.duration-unlimited",
                        f"Promocode '{promocode.code}' cannot extend unlimited subscription",
                    )

                base_date = max(subscription.expire_at, datetime_now())
                subscription.expire_at = base_date + timedelta(days=reward)
                await self.subscription_dao.update(subscription)
                await self.remnawave.update_user(
                    user=user,
                    uuid=subscription.user_remna_id,
                    subscription=subscription,
                )
            case PromocodeRewardType.TRAFFIC:
                applied_discount = 0
                subscription = await self._require_subscription(user.telegram_id, promocode)

                if subscription.traffic_limit == 0:
                    raise PromocodeError(
                        "ntf-promocode.traffic-unlimited",
                        f"Promocode '{promocode.code}' cannot extend unlimited traffic",
                    )

                subscription.traffic_limit += reward
                await self.subscription_dao.update(subscription)
                await self.remnawave.update_user(
                    user=user,
                    uuid=subscription.user_remna_id,
                    subscription=subscription,
                )
            case _:
                raise PromocodeError(
                    "ntf-promocode.unsupported",
                    f"Promocode reward type '{promocode.reward_type}' is not supported yet",
                )

        return applied_discount

    async def _disable_promocode(self, promocode: PromocodeDto, commit: bool = True) -> None:
        if promocode.is_active:
            promocode.is_active = False
            await self.promocode_dao.update(promocode.as_fully_changed())

        if commit:
            await self.uow.commit()

    async def _require_subscription(
        self,
        telegram_id: int,
        promocode: PromocodeDto,
    ) -> SubscriptionDto:
        subscription = await self.subscription_dao.get_current(telegram_id)
        if subscription is None:
            raise PromocodeError(
                "ntf-promocode.subscription-required",
                f"Promocode '{promocode.code}' requires an active subscription",
            )

        return subscription
