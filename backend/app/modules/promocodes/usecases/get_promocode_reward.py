from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import AddOnRepository, PlanRepository
from app.modules.promocodes.availability import get_usable_promocode
from app.modules.promocodes.dto import PromocodeRewardDto, ValidatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto


class GetPromocodeRewardUseCase(UseCase[ValidatePromocodeDto, PromocodeRewardDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        addon_repository: AddOnRepository,
        plan_repository: PlanRepository,
        uow: UnitOfWork,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._addon_repository = addon_repository
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ValidatePromocodeDto) -> PromocodeRewardDto:
        async with self._uow:
            promo = await get_usable_promocode(self._promocode_repository, data.code)
            if promo.reward_addon_id is not None and promo.reward_type in (
                PromocodeRewardType.TRAFFIC,
                PromocodeRewardType.DEVICES,
            ):
                addon = await self._addon_repository.get_by_id(promo.reward_addon_id)
                return PromocodeRewardDto(reward_type=promo.reward_type, amount=addon.amount)
            if promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
                assert promo.reward_plan_id is not None
                plan = await self._plan_repository.get_by_id(promo.reward_plan_id)
                return PromocodeRewardDto(
                    reward_type=promo.reward_type,
                    amount=promo.reward_duration_days,
                    plan_name=plan.name,
                )
            return PromocodeRewardDto(reward_type=promo.reward_type, amount=promo.reward)
