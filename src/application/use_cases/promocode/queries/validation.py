from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PromocodeDao, SubscriptionDao
from src.application.common.policy import Permission
from src.application.dto import PromocodeDto, UserDto
from src.core.enums import PromoAudience
from src.core.exceptions import (
    PromocodeAudienceMismatchError,
    PromocodeAlreadyUsedError,
    PromocodeExpiredError,
    PromocodeInactiveError,
    PromocodeLimitExceededError,
    PromocodeNotFoundError,
    PromocodePlanMismatchError,
)


@dataclass(frozen=True)
class GetPromocodeDto:
    code: str


class GetPromocode(Interactor[GetPromocodeDto, PromocodeDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, promocode_dao: PromocodeDao) -> None:
        self.promocode_dao = promocode_dao

    async def _execute(self, actor: UserDto, data: GetPromocodeDto) -> PromocodeDto:
        promocode = await self.promocode_dao.get_by_code(data.code)

        if not promocode:
            logger.debug(f"{actor.log} Promocode '{data.code}' not found")
            raise PromocodeNotFoundError

        logger.debug(f"{actor.log} Promocode '{data.code}' retrieved (id={promocode.id})")
        return promocode


@dataclass(frozen=True)
class ValidatePromocodeDto:
    code: str
    plan_id: int
    user_telegram_id: int


class ValidatePromocode(Interactor[ValidatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_dao: PromocodeDao,
        subscription_dao: SubscriptionDao,
    ) -> None:
        self.promocode_dao = promocode_dao
        self.subscription_dao = subscription_dao

    async def _execute(self, actor: UserDto, data: ValidatePromocodeDto) -> PromocodeDto:
        promocode = await self.promocode_dao.get_by_code(data.code)

        if not promocode:
            logger.debug(f"{actor.log} Promocode '{data.code}' not found")
            raise PromocodeNotFoundError

        if promocode.id is None:
            raise PromocodeNotFoundError

        promocode_id: int = promocode.id

        if not promocode.is_active:
            logger.debug(f"{actor.log} Promocode '{data.code}' is inactive")
            raise PromocodeInactiveError

        now = datetime.now(tz=timezone.utc)
        if promocode.expires_at.replace(tzinfo=timezone.utc) < now:
            logger.debug(f"{actor.log} Promocode '{data.code}' has expired")
            raise PromocodeExpiredError

        if promocode.plan_id != data.plan_id:
            logger.debug(
                f"{actor.log} Promocode '{data.code}' is bound to plan_id='{promocode.plan_id}', "
                f"got plan_id='{data.plan_id}'"
            )
            raise PromocodePlanMismatchError

        activation_count = await self.promocode_dao.count_activations(promocode_id)
        if activation_count >= promocode.max_activations:
            logger.debug(
                f"{actor.log} Promocode '{data.code}' has reached max activations "
                f"({activation_count}/{promocode.max_activations})"
            )
            raise PromocodeLimitExceededError

        already_used = await self.promocode_dao.has_user_activated(
            promocode_id,
            data.user_telegram_id,
        )
        if already_used:
            logger.debug(
                f"{actor.log} User '{data.user_telegram_id}' already used "
                f"promocode '{data.code}'"
            )
            raise PromocodeAlreadyUsedError

        if promocode.audience != PromoAudience.ALL:
            subscription = await self.subscription_dao.get_current(data.user_telegram_id)
            has_subscription = subscription is not None

            if promocode.audience == PromoAudience.WITH_ACTIVE_SUBSCRIPTION and not has_subscription:
                logger.debug(
                    f"{actor.log} Promocode '{data.code}' requires active subscription, "
                    f"user '{data.user_telegram_id}' has none"
                )
                raise PromocodeAudienceMismatchError

            if promocode.audience == PromoAudience.WITHOUT_ACTIVE_SUBSCRIPTION and has_subscription:
                logger.debug(
                    f"{actor.log} Promocode '{data.code}' requires no active subscription, "
                    f"user '{data.user_telegram_id}' has one"
                )
                raise PromocodeAudienceMismatchError

        logger.info(
            f"{actor.log} Promocode '{data.code}' validated successfully "
            f"for user '{data.user_telegram_id}'"
        )
        return promocode
