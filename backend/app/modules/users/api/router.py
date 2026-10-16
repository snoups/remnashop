from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import error_responses
from app.core.constants import CABINET_API_PREFIX, TIME_1M
from app.modules.users.usecases import UnsubscribeMarketingUseCase

# RFC 8058 one-click POSTs arrive from a few shared mail-provider IPs; the token is an HMAC
_UNSUBSCRIBE_LIMIT_PER_MINUTE: Final[int] = 600

router = APIRouter(prefix=CABINET_API_PREFIX, tags=["cabinet"])


# POST only: mail scanners open links, and RFC 8058 clients POST here themselves
@router.post(
    "/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(
            rate_limit(
                key="cabinet_unsubscribe",
                limit=_UNSUBSCRIBE_LIMIT_PER_MINUTE,
                window_seconds=TIME_1M,
            )
        )
    ],
    responses=error_responses(400),
)
@inject
async def unsubscribe_marketing(
    use_case: FromDishka[UnsubscribeMarketingUseCase],
    token: str = Query(..., max_length=128),
) -> None:
    await use_case.execute(token)
