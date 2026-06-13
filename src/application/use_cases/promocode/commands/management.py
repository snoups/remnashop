from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PromocodeDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import PromocodeActivationDto, PromocodeDto, UserDto
from src.core.enums import PromoAudience
from src.core.exceptions import (
    PromocodeInvalidDiscountError,
    PromocodeInvalidMaxActivationsError,
    PromocodeNotFoundError,
)


@dataclass(frozen=True)
class CreatePromocodeDto:
    code: str
    discount_percent: int
    plan_id: int
    audience: PromoAudience
    max_activations: int
    expires_at: datetime


class CreatePromocode(Interactor[CreatePromocodeDto, PromocodeDto]):
    required_permission = Permission.REMNASHOP_PROMOCODE_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        promocode_dao: PromocodeDao,
    ) -> None:
        self.uow = uow
        self.promocode_dao = promocode_dao

    async def _execute(self, actor: UserDto, data: CreatePromocodeDto) -> PromocodeDto:
        if not (1 <= data.discount_percent <= 99):
            logger.debug(
                f"{actor.log} Invalid discount_percent '{data.discount_percent}' "
                f"for promocode '{data.code}'"
            )
            raise PromocodeInvalidDiscountError

        if data.max_activations < 1:
            logger.debug(
                f"{actor.log} Invalid max_activations '{data.max_activations}' "
                f"for promocode '{data.code}'"
            )
            raise PromocodeInvalidMaxActivationsError

        async with self.uow:
            promocode = await self.promocode_dao.create(
                PromocodeDto(
                    code=data.code,
                    discount_percent=data.discount_percent,
                    plan_id=data.plan_id,
                    audience=data.audience,
                    max_activations=data.max_activations,
                    expires_at=data.expires_at,
                    is_active=True,
                )
            )
            await self.uow.commit()

        logger.info(
            f"{actor.log} Created promocode '{data.code}' "
            f"discount={data.discount_percent}% plan_id={data.plan_id}"
        )
        return promocode


@dataclass(frozen=True)
class DeactivatePromocodeDto:
    promocode_id: int


class DeactivatePromocode(Interactor[DeactivatePromocodeDto, None]):
    required_permission = Permission.REMNASHOP_PROMOCODE_EDITOR

    def __init__(
        self,
        uow: UnitOfWork,
        promocode_dao: PromocodeDao,
    ) -> None:
        self.uow = uow
        self.promocode_dao = promocode_dao

    async def _execute(self, actor: UserDto, data: DeactivatePromocodeDto) -> None:
        promocode = await self.promocode_dao.get_by_id(data.promocode_id)

        if not promocode:
            logger.debug(f"{actor.log} Promocode id='{data.promocode_id}' not found")
            raise PromocodeNotFoundError

        async with self.uow:
            await self.promocode_dao.deactivate(data.promocode_id)
            await self.uow.commit()

        logger.info(f"{actor.log} Deactivated promocode id='{data.promocode_id}'")


@dataclass(frozen=True)
class RecordPromocodeActivationDto:
    promocode_id: int
    user_telegram_id: int
    transaction_payment_id: UUID


class RecordPromocodeActivation(Interactor[RecordPromocodeActivationDto, PromocodeActivationDto]):
    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        promocode_dao: PromocodeDao,
    ) -> None:
        self.uow = uow
        self.promocode_dao = promocode_dao

    async def _execute(
        self,
        actor: UserDto,
        data: RecordPromocodeActivationDto,
    ) -> PromocodeActivationDto:
        async with self.uow:
            activation = await self.promocode_dao.record_activation(
                PromocodeActivationDto(
                    promocode_id=data.promocode_id,
                    user_telegram_id=data.user_telegram_id,
                    transaction_payment_id=data.transaction_payment_id,
                )
            )
            await self.uow.commit()

        logger.info(
            f"{actor.log} Recorded promocode activation: "
            f"promocode_id='{data.promocode_id}' user='{data.user_telegram_id}' "
            f"payment='{data.transaction_payment_id}'"
        )
        return activation
