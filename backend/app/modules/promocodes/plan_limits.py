from collections.abc import Iterable
from typing import Final

from app.core.enums import PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.plans import PlanRepository

# rewards applied to a subscription the customer picks; only these honour a plan list
PLAN_LIMITED_REWARDS: Final[frozenset[PromocodeRewardType]] = frozenset(
    {PromocodeRewardType.DURATION, PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES}
)


async def check_allowed_plans(
    reward_type: PromocodeRewardType,
    plan_ids: list[int],
    plan_repository: PlanRepository,
    *,
    already_stored: Iterable[int] = (),
) -> list[int]:
    """The list to store. An unknown id the promocode already held (its plan
    was deleted) is dropped; a newly added unknown one is refused."""
    if not plan_ids:
        return []
    if reward_type not in PLAN_LIMITED_REWARDS:
        raise ValidationError(
            f"A plan list doesn't apply to '{reward_type.value}' promocodes",
            code=ErrorCode.PROMOCODE_PLANS_NOT_APPLICABLE,
        )
    known = {plan.id for plan in await plan_repository.list_all()}
    missing = sorted(set(plan_ids) - known - set(already_stored))
    if missing:
        raise NotFoundError(f"Plans {missing} not found", code=ErrorCode.PLAN_NOT_FOUND)
    return [plan_id for plan_id in plan_ids if plan_id in known]
