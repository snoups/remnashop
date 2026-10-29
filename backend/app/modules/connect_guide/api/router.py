from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response

from app.api.dependencies.rate_limit import rate_limit
from app.core.config import AppConfig
from app.core.constants import TIME_1M
from app.core.security.connect_signature import verify_connect_signature
from app.modules.connect_guide.api.schemas import (
    ConnectHandoffVerifyRequest,
    ConnectHandoffVerifyResponse,
    PublicConnectGuideResponse,
)
from app.modules.connect_guide.usecases import GetPublicConnectGuideUseCase

# zero-session: the page a Mini App deep link opens in the browser has no cabinet session
router = APIRouter(prefix="/shop", tags=["connect-guide"])


@router.get(
    "/connect-guide",
    response_model=PublicConnectGuideResponse,
    dependencies=[Depends(rate_limit(key="connect_guide", limit=60, window_seconds=TIME_1M))],
)
@inject
async def get_public_connect_guide(
    use_case: FromDishka[GetPublicConnectGuideUseCase],
) -> PublicConnectGuideResponse:
    catalog = await use_case.execute()
    return PublicConnectGuideResponse(platforms=catalog.platforms)


@router.post(
    "/connect-guide/verify",
    response_model=ConnectHandoffVerifyResponse,
    dependencies=[Depends(rate_limit(key="connect_handoff", limit=30, window_seconds=TIME_1M))],
)
@inject
async def verify_connect_handoff(
    body: ConnectHandoffVerifyRequest,
    response: Response,
    config: FromDishka[AppConfig],
) -> ConnectHandoffVerifyResponse:
    response.headers["Cache-Control"] = "no-store"
    valid = verify_connect_signature(
        body.digest, body.signature, config.jwt_secret.get_secret_value()
    )
    return ConnectHandoffVerifyResponse(valid=valid)
