from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.availability import assert_available_to, get_usable_promocode
from app.modules.promocodes.dto import ListPromocodeTargetsDto
from app.modules.promocodes.plan_limits import PLAN_LIMITED_REWARDS
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.targets import PromocodeTargets
from app.modules.subscriptions import ReferrerLookup, SubscriptionDto, SubscriptionRepository
from app.modules.users import UserDto


class ListPromocodeTargetsUseCase(UseCase[ListPromocodeTargetsDto, list[SubscriptionDto], UserDto]):
    """The customer's subscriptions a promocode's reward can go to, by the
    rule the activation applies; none for a reward that takes no subscription."""

    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        subscription_repository: SubscriptionRepository,
        referrer_lookup: ReferrerLookup,
        targets: PromocodeTargets,
        uow: UnitOfWork,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._referrer_lookup = referrer_lookup
        self._targets = targets
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: ListPromocodeTargetsDto
    ) -> list[SubscriptionDto]:
        async with self._uow:
            promo = await get_usable_promocode(self._promocode_repository, data.code)
        await assert_available_to(
            promo, actor, self._subscription_repository, self._referrer_lookup
        )
        if promo.reward_type not in PLAN_LIMITED_REWARDS:
            return []

        async with self._uow:
            # EXPIRED included: days can bring one back
            subscriptions = await self._subscription_repository.get_live_by_user(actor.id)
        # the panel is asked outside the transaction, one at a time: a customer has a few
        return [
            subscription
            for subscription in subscriptions
            if await self._targets.takes_reward(promo, subscription)
            and await self._targets.plan_accepts(promo, subscription)
        ]
