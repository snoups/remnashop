import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PlanType
from app.modules.advertising.repository import AdLinkRepository
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.transactions.repository import TransactionRepository


@pytest.fixture
def ad_link_repository(session: AsyncSession) -> AdLinkRepository:
    return AdLinkRepository(session)


@pytest.fixture
def transaction_repository(session: AsyncSession) -> TransactionRepository:
    return TransactionRepository(session)


@pytest.fixture
async def plan_id(plan_repository: PlanRepository) -> int:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="ad-link-test-plan",
            name="Ad Link Test Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    return plan.id
