from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.enums import PaymentGatewayType
from app.modules.gateways.api.schemas import (
    GatewayCatalogEntryResponse,
    GatewayCatalogResponse,
    GatewayFieldSpecResponse,
    GatewayListResponse,
    GatewayResponse,
    ReorderGatewaysRequest,
    UpdateGatewaySettingsRequest,
)
from app.modules.gateways.dto import (
    ReorderGatewaysDto,
    SetGatewayActiveDto,
    UpdateGatewaySettingsDto,
)
from app.modules.gateways.field_catalog import GATEWAY_FIELD_CATALOG
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    SetGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)

router = APIRouter(prefix="/gateways", tags=["gateways"])


@router.get("", response_model=GatewayListResponse)
@inject
async def list_gateways(
    use_case: FromDishka[ListGatewaysUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayListResponse:
    gateways = await use_case(actor)
    items = [GatewayResponse.model_validate(gateway, from_attributes=True) for gateway in gateways]
    return GatewayListResponse(items=items, total=len(items))


@router.get("/catalog", response_model=GatewayCatalogResponse)
@inject
async def get_gateway_catalog(
    config: FromDishka[AppConfig],
    actor: Actor = Depends(require_admin_user),
) -> GatewayCatalogResponse:
    # Static schema metadata, no secrets -- no usecase/Permission layer, so
    # dashboard sessions only, same as GET /permissions/catalog.
    return GatewayCatalogResponse(
        entries=[
            GatewayCatalogEntryResponse(
                type=gateway_type,
                # payments go through the bot, not an inbound callback
                webhook_url=(
                    None
                    if gateway_type == PaymentGatewayType.TELEGRAM_STARS
                    else config.get_webhook(gateway_type)
                ),
                fields=[
                    GatewayFieldSpecResponse(
                        key=field_spec.key,
                        kind=field_spec.kind.value,
                        required=field_spec.required,
                    )
                    for field_spec in field_specs
                ],
            )
            for gateway_type, field_specs in GATEWAY_FIELD_CATALOG.items()
        ]
    )


@router.put(
    "/{gateway_type}/settings", response_model=GatewayResponse, responses=error_responses(400)
)
@inject
async def update_gateway_settings(
    gateway_type: PaymentGatewayType,
    payload: UpdateGatewaySettingsRequest,
    use_case: FromDishka[UpdateGatewaySettingsUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayResponse:
    gateway = await use_case(
        actor, UpdateGatewaySettingsDto(type=gateway_type, values=payload.values)
    )
    return GatewayResponse.model_validate(gateway, from_attributes=True)


@router.post(
    "/{gateway_type}/actions/enable", response_model=GatewayResponse, responses=error_responses(400)
)
@inject
async def enable_gateway(
    gateway_type: PaymentGatewayType,
    use_case: FromDishka[SetGatewayActiveUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayResponse:
    gateway = await use_case(actor, SetGatewayActiveDto(type=gateway_type, is_active=True))
    return GatewayResponse.model_validate(gateway, from_attributes=True)


@router.post("/{gateway_type}/actions/disable", response_model=GatewayResponse)
@inject
async def disable_gateway(
    gateway_type: PaymentGatewayType,
    use_case: FromDishka[SetGatewayActiveUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayResponse:
    gateway = await use_case(actor, SetGatewayActiveDto(type=gateway_type, is_active=False))
    return GatewayResponse.model_validate(gateway, from_attributes=True)


@router.post("/actions/reorder", response_model=GatewayListResponse, responses=error_responses(400))
@inject
async def reorder_gateways(
    payload: ReorderGatewaysRequest,
    use_case: FromDishka[ReorderGatewaysUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayListResponse:
    gateways = await use_case(actor, ReorderGatewaysDto(ordered_types=payload.types))
    items = [GatewayResponse.model_validate(gateway, from_attributes=True) for gateway in gateways]
    return GatewayListResponse(items=items, total=len(items))
