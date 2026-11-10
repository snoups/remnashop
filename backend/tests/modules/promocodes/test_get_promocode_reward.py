from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, PlanType, PromocodeRewardType
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import CreateAddOnDto, CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.promocodes.dto import CreatePromocodeDto, ValidatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import GetPromocodeRewardUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_reward_reads_addon_amount_and_plan_name(
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    session = promocode_repository.session
    addons = AddOnRepository(session)
    plans = PlanRepository(session)
    addon = await addons.create(
        CreateAddOnDto(name="+50 GB", type=AddOnType.TRAFFIC, amount=50, base_price=Decimal(1))
    )
    plan = await plans.create(
        CreatePlanDto(
            public_code="promo-reward",
            name="Премиум",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="GB50", reward_type=PromocodeRewardType.TRAFFIC, reward_addon_id=addon.id
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="PLAN30",
            reward_type=PromocodeRewardType.SUBSCRIPTION,
            reward_plan_id=plan.id,
            reward_duration_days=30,
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="OFF15", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=15
        )
    )
    actor = await user_repository.create(CreateUserDto(name="reward-viewer"))
    use_case = GetPromocodeRewardUseCase(promocode_repository, addons, plans, uow)

    traffic = await use_case(actor, ValidatePromocodeDto(code="gb50"))
    subscription = await use_case(actor, ValidatePromocodeDto(code="PLAN30"))
    discount = await use_case(actor, ValidatePromocodeDto(code="OFF15"))

    assert (traffic.reward_type, traffic.amount) == (PromocodeRewardType.TRAFFIC, 50)
    assert (subscription.amount, subscription.plan_name) == (30, "Премиум")
    assert (discount.amount, discount.plan_name) == (15, None)
