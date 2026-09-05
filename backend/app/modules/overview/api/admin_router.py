from enum import IntEnum
from typing import cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.modules.overview.api.schemas import (
    DailyAmountResponse,
    DailyCountResponse,
    OverviewPaymentsResponse,
    OverviewResponse,
    OverviewSubscriptionsResponse,
    OverviewUsersResponse,
)
from app.modules.overview.dto import GetOverviewDto, OverviewDays
from app.modules.overview.usecases import GetOverviewUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/overview", tags=["overview"])


class OverviewPeriodDays(IntEnum):
    # FastAPI (0.127.0) + Pydantic v2 (2.11.10) doesn't coerce a query
    # string into an int-typed Literal[7, 30, 90] -- `?days=7` 422s with
    # "Input should be 7, 30 or 90" even for a valid value, because the raw
    # query value arrives as the string "7" and Literal validation requires
    # an exact type match against its int members. An IntEnum query param
    # coerces correctly (confirmed against this exact FastAPI/Pydantic
    # version pair) where Literal[int, ...] does not -- this is why the
    # route below takes an IntEnum, converted back to the OverviewDays
    # Literal only when building GetOverviewDto (the usecase's own contract,
    # unaffected by this router-boundary issue).
    SEVEN = 7
    THIRTY = 30
    NINETY = 90


@router.get("", response_model=OverviewResponse)
@inject
async def get_overview(
    use_case: FromDishka[GetOverviewUseCase],
    actor: UserDto = Depends(require_admin),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> OverviewResponse:
    overview = await use_case(actor, GetOverviewDto(days=cast(OverviewDays, int(days))))
    return OverviewResponse(
        days=overview.days,
        users=(
            OverviewUsersResponse(
                total=overview.users.total,
                new_today=overview.users.new_today,
                daily_registrations=[
                    DailyCountResponse(day=d.day, count=d.count)
                    for d in overview.users.daily_registrations
                ],
            )
            if overview.users is not None
            else None
        ),
        subscriptions=(
            OverviewSubscriptionsResponse(active=overview.subscriptions.active)
            if overview.subscriptions is not None
            else None
        ),
        payments=(
            OverviewPaymentsResponse(
                paid_orders_count=overview.payments.paid_orders_count,
                revenue_by_currency=overview.payments.revenue_by_currency,
                report_currency=overview.payments.report_currency,
                daily_revenue=[
                    DailyAmountResponse(day=d.day, amount=d.amount)
                    for d in overview.payments.daily_revenue
                ],
            )
            if overview.payments is not None
            else None
        ),
    )
