from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, RemnawavePanelUnavailableError, ValidationError
from app.modules.plans import PlanRepository
from app.modules.subscriptions import PanelTrafficUsage, SubscriptionDto, traffic_spent_for_good


class BonusDaysTargets:
    """Which subscription bonus days may extend: shared by the redemption and
    the list a customer picks from, so the list never offers one the
    redemption then refuses."""

    def __init__(
        self, plan_repository: PlanRepository, usage: PanelTrafficUsage, uow: UnitOfWork
    ) -> None:
        self._plan_repository = plan_repository
        self._usage = usage
        self._uow = uow

    async def accepts(self, target: SubscriptionDto) -> bool:
        try:
            await self.assert_accepts(target)
        except (ValidationError, RemnawavePanelUnavailableError):
            return False
        return True

    async def assert_accepts(self, target: SubscriptionDto) -> None:
        if target.is_trial:
            raise ValidationError(
                "Bonus days can't extend a trial", code=ErrorCode.BONUS_DAYS_TRIAL_SUBSCRIPTION
            )
        if target.status is SubscriptionStatus.DELETED:
            raise ValidationError(
                "Cannot renew a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
            )
        # disabled on purpose; a free extension mustn't undo that (the renewal
        # re-checks it right before touching the panel)
        if target.status is SubscriptionStatus.DISABLED:
            raise ValidationError(
                "Bonus days can't extend a disabled subscription",
                code=ErrorCode.BONUS_DAYS_SUBSCRIPTION_DISABLED,
            )
        async with self._uow:
            try:
                plan = await self._plan_repository.get_by_id(target.plan_snapshot.plan_id)
            except NotFoundError:
                plan = None  # a deleted plan keeps the defaults: allowed
        if plan is not None and not plan.allow_bonus_days:
            raise ValidationError(
                "The subscription's plan doesn't accept bonus days",
                code=ErrorCode.BONUS_DAYS_PLAN_NOT_ALLOWED,
            )
        if target.status is SubscriptionStatus.ACTIVE:
            return
        # days on an EXPIRED or LIMITED one are wasted if its traffic never comes back
        used = await self._usage.used_traffic(target)
        if used is None:
            raise RemnawavePanelUnavailableError("Can't read the subscription's traffic usage")
        if traffic_spent_for_good(target, used):
            raise ValidationError(
                "The subscription's traffic is spent and never resets",
                code=ErrorCode.BONUS_DAYS_TRAFFIC_SPENT,
            )
