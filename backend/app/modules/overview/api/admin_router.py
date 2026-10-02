from enum import IntEnum
from typing import cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.core.actor import Actor
from app.modules.overview.api.schemas import (
    OverviewResponse,
)
from app.modules.overview.dto import GetOverviewDto, OverviewDays
from app.modules.overview.usecases import GetOverviewUseCase

router = APIRouter(prefix="/overview", tags=["overview"])


class OverviewPeriodDays(IntEnum):
    # a query string isn't coerced into Literal[7, 30, 90] (`?days=7` 422s), an
    # IntEnum is; mapped back to OverviewDays when building GetOverviewDto
    ALL = 0
    SEVEN = 7
    THIRTY = 30
    NINETY = 90


@router.get("", response_model=OverviewResponse)
@inject
async def get_overview(
    use_case: FromDishka[GetOverviewUseCase],
    actor: Actor = Depends(require_admin),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> OverviewResponse:
    overview = await use_case(actor, GetOverviewDto(days=cast(OverviewDays, int(days))))
    return OverviewResponse.model_validate(overview, from_attributes=True)
