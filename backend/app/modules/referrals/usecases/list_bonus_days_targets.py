from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.bonus_targets import BonusDaysTargets
from app.modules.subscriptions import SubscriptionDto, SubscriptionRepository
from app.modules.users import UserDto


class ListBonusDaysTargetsUseCase(UseCase[None, list[SubscriptionDto], UserDto]):
    """The customer's subscriptions bonus days can extend, by the rule the
    redemption applies."""

    required_permission = Permission.PUBLIC

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        targets: BonusDaysTargets,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._targets = targets
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[SubscriptionDto]:
        async with self._uow:
            # EXPIRED included: days bring one back
            subscriptions = await self._subscription_repository.get_live_by_user(actor.id)
        # the panel is asked outside the transaction, one at a time: a customer has a few
        return [s for s in subscriptions if await self._targets.accepts(s)]
