from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request

from app.api.dependencies.admin import require_admin
from app.core.actor import Actor
from app.core.utils.http import resolve_client_ip
from app.modules.connect_guide.api.schemas import ConnectGuideRequest, ConnectGuideResponse
from app.modules.connect_guide.dto import ResetConnectGuideDto, UpdateConnectGuideDto
from app.modules.connect_guide.usecases import (
    GetConnectGuideUseCase,
    ResetConnectGuideUseCase,
    UpdateConnectGuideUseCase,
)

router = APIRouter(prefix="/connect-guide", tags=["connect-guide"])


@router.get("", response_model=ConnectGuideResponse)
@inject
async def get_connect_guide(
    use_case: FromDishka[GetConnectGuideUseCase],
    actor: Actor = Depends(require_admin),
) -> ConnectGuideResponse:
    return ConnectGuideResponse.model_validate(await use_case(actor), from_attributes=True)


@router.put("", response_model=ConnectGuideResponse)
@inject
async def update_connect_guide(
    payload: ConnectGuideRequest,
    request: Request,
    use_case: FromDishka[UpdateConnectGuideUseCase],
    actor: Actor = Depends(require_admin),
) -> ConnectGuideResponse:
    saved = await use_case(
        actor,
        UpdateConnectGuideDto(
            enabled=payload.enabled,
            catalog=payload.catalog,
            client_ip=resolve_client_ip(request),
        ),
    )
    return ConnectGuideResponse.model_validate(saved, from_attributes=True)


@router.post("/actions/reset", response_model=ConnectGuideResponse)
@inject
async def reset_connect_guide(
    request: Request,
    use_case: FromDishka[ResetConnectGuideUseCase],
    actor: Actor = Depends(require_admin),
) -> ConnectGuideResponse:
    settings = await use_case(actor, ResetConnectGuideDto(client_ip=resolve_client_ip(request)))
    return ConnectGuideResponse.model_validate(settings, from_attributes=True)
