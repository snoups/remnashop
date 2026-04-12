from dataclasses import dataclass
from typing import Optional

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PlanDao, SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.dto import UserDto
from src.core.enums import BroadcastAudience


@dataclass(frozen=True)
class GetBroadcastAudienceCountDto:
    audience: BroadcastAudience
    plan_id: Optional[int] = None


class GetBroadcastAudienceCount(Interactor[GetBroadcastAudienceCountDto, int]):
    required_permission = Permission.BROADCAST

    def __init__(
        self,
        user_dao: UserDao,
        plan_dao: PlanDao,
        subscription_dao: SubscriptionDao,
    ) -> None:
        self.user_dao = user_dao
        self.plan_dao = plan_dao
        self.subscription_dao = subscription_dao

    async def _execute(self, actor: UserDto, data: GetBroadcastAudienceCountDto) -> int:
        audience = data.audience
        plan_id = data.plan_id

        if audience == BroadcastAudience.PLAN:
            if plan_id:
                count = await self.subscription_dao.count_active_by_plan(plan_id)
            else:
                count = await self.plan_dao.count_non_trial()

        elif audience == BroadcastAudience.ALL:
            count = await self.user_dao.count_active_non_blocked()

        elif audience == BroadcastAudience.SUBSCRIBED:
            count = await self.user_dao.count_with_active_subscription()

        elif audience == BroadcastAudience.UNSUBSCRIBED:
            count = await self.user_dao.count_without_subscription()

        elif audience == BroadcastAudience.EXPIRED:
            count = await self.user_dao.count_with_expired_subscription()

        elif audience == BroadcastAudience.TRIAL:
            count = await self.user_dao.count_with_trial_subscription()

        else:
            logger.error(f"{actor.log} Received unknown broadcast audience '{audience}'")
            raise ValueError(f"Unknown broadcast audience '{audience}'")

        logger.info(f"{actor.log} Counted audience '{audience}' (plan_id='{plan_id}'): '{count}'")
        return count


@dataclass(frozen=True)
class GetBroadcastAudienceUsersDto:
    audience: BroadcastAudience
    plan_id: Optional[int] = None


class GetBroadcastAudienceUsers(Interactor[GetBroadcastAudienceUsersDto, list[UserDto]]):
    required_permission = Permission.BROADCAST

    def __init__(self, user_dao: UserDao) -> None:
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: GetBroadcastAudienceUsersDto) -> list[UserDto]:
        audience = data.audience
        plan_id = data.plan_id

        if audience == BroadcastAudience.PLAN and plan_id:
            users = await self.user_dao.get_active_by_plan(plan_id)
        elif audience == BroadcastAudience.ALL:
            users = await self.user_dao.get_active_non_blocked()
        elif audience == BroadcastAudience.SUBSCRIBED:
            users = await self.user_dao.get_with_active_subscription()
        elif audience == BroadcastAudience.UNSUBSCRIBED:
            users = await self.user_dao.get_without_subscription()
        elif audience == BroadcastAudience.EXPIRED:
            users = await self.user_dao.get_with_expired_subscription()
        elif audience == BroadcastAudience.TRIAL:
            users = await self.user_dao.get_with_trial_subscription()
        else:
            logger.error(f"{actor.log} Received unknown broadcast audience '{audience}'")
            raise ValueError(f"Unknown broadcast audience '{audience}'")

        logger.info(f"{actor.log} Retrieved '{len(users)}' users for audience '{audience}'")
        return users
