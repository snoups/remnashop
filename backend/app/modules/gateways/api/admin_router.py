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
    GatewayTestPaymentResponse,
    GatewayTestPaymentStatusResponse,
    ReorderGatewaysRequest,
    UpdateGatewaySettingsRequest,
)
from app.modules.gateways.dto import (
    PaymentGatewayDto,
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
from app.modules.transactions import CreateTestPaymentUseCase, GetTestPaymentStatusUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/gateways", tags=["gateways"])


def _to_response(gateway: PaymentGatewayDto) -> GatewayResponse:
    return GatewayResponse(
        type=gateway.type,
        order_index=gateway.order_index,
        is_active=gateway.is_active,
        is_configured=gateway.is_configured,
        flags=gateway.flags,
    )


@router.get("", response_model=GatewayListResponse)
@inject
async def list_gateways(
    use_case: FromDishka[ListGatewaysUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayListResponse:
    gateways = await use_case(actor)
    items = [_to_response(gateway) for gateway in gateways]
    return GatewayListResponse(items=items, total=len(items))


@router.get("/catalog", response_model=GatewayCatalogResponse)
@inject
async def get_gateway_catalog(
    config: FromDishka[AppConfig],
    actor: Actor = Depends(require_admin),
) -> GatewayCatalogResponse:
    # Static schema metadata, no secrets -- no usecase/Permission layer,
    # same precedent as GET /permissions/catalog in app/api/app.py.
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
    return _to_response(gateway)


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
    return _to_response(gateway)


@router.post("/{gateway_type}/actions/disable", response_model=GatewayResponse)
@inject
async def disable_gateway(
    gateway_type: PaymentGatewayType,
    use_case: FromDishka[SetGatewayActiveUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayResponse:
    gateway = await use_case(actor, SetGatewayActiveDto(type=gateway_type, is_active=False))
    return _to_response(gateway)


@router.post(
    "/{gateway_type}/actions/test",
    response_model=GatewayTestPaymentResponse,
    responses=error_responses(400, 502),
)
@inject
async def create_test_payment(
    gateway_type: PaymentGatewayType,
    use_case: FromDishka[CreateTestPaymentUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> GatewayTestPaymentResponse:
    result = await use_case(actor, gateway_type)
    return GatewayTestPaymentResponse(
        order_id=result.order_id, confirmation_url=result.confirmation_url
    )


@router.get(
    "/test-payments/{order_id}",
    response_model=GatewayTestPaymentStatusResponse,
    responses=error_responses(404),
)
@inject
async def get_test_payment_status(
    order_id: int,
    use_case: FromDishka[GetTestPaymentStatusUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayTestPaymentStatusResponse:
    order_status = await use_case(actor, order_id)
    return GatewayTestPaymentStatusResponse(status=order_status)


@router.post("/actions/reorder", response_model=GatewayListResponse, responses=error_responses(400))
@inject
async def reorder_gateways(
    payload: ReorderGatewaysRequest,
    use_case: FromDishka[ReorderGatewaysUseCase],
    actor: Actor = Depends(require_admin),
) -> GatewayListResponse:
    gateways = await use_case(actor, ReorderGatewaysDto(ordered_types=payload.types))
    items = [_to_response(gateway) for gateway in gateways]
    return GatewayListResponse(items=items, total=len(items))
