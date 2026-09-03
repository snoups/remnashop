import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PlanType
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
def payment_order_repository(session: AsyncSession) -> PaymentOrderRepository:
    return PaymentOrderRepository(session)


@pytest.fixture
async def user_id(user_repository: UserRepository) -> int:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=900_001))
    return user.id


@pytest.fixture
async def plan_id(plan_repository: PlanRepository) -> int:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="payment-order-test-plan",
            name="Payment Order Test Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    return plan.id
