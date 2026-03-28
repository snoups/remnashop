from dataclasses import dataclass
from datetime import timedelta

from loguru import logger

from src.application.common import EventPublisher, Interactor
from src.application.common.dao import PromocodeDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import (
    ActivatePromocodeResultDto,
    PromocodeActivationDto,
    PromocodeDto,
    UserDto,
)
from src.application.events import PromocodeActivatedEvent
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
        event_publisher: EventPublisher,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.promocode_dao = promocode_dao
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

            if (
                promocode.lifetime is not None
                and promocode.created_at is not None
                and promocode.created_at + timedelta(days=promocode.lifetime) < datetime_now()
            ):
                raise PromocodeError(
                    "ntf-promocode.expired",
                    f"Promocode '{normalized_code}' is expired",
                )

            if promocode.max_activations is not None:
                activations = await self.promocode_dao.count_activations(promocode.id)
                if activations >= promocode.max_activations:
                    raise PromocodeError(
                        "ntf-promocode.limit-reached",
                        f"Promocode '{normalized_code}' reached activation limit",
                    )

            applied_discount = self._apply_reward(user, promocode)
            updated_user = await self.user_dao.update(user) or user

            await self.promocode_dao.create_activation(
                PromocodeActivationDto(
                    promocode_id=promocode.id,
                    user_telegram_id=updated_user.telegram_id,
                )
            )
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
            )
        )

        logger.info(
            f"{updated_user.log} Activated promocode '{promocode.code}' "
            f"with type '{promocode.reward_type}' and reward '{applied_discount}'"
        )

        return ActivatePromocodeResultDto(
            user=updated_user,
            code=promocode.code,
            promocode_type=promocode.reward_type,
            reward=promocode.reward or applied_discount,
            applied_discount=applied_discount,
        )

    def _apply_reward(self, user: UserDto, promocode: PromocodeDto) -> int:
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
            case _:
                raise PromocodeError(
                    "ntf-promocode.unsupported",
                    f"Promocode reward type '{promocode.reward_type}' is not supported yet",
                )

        return applied_discount
