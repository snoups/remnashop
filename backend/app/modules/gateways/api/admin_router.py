from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.admin import require_admin
from app.core.config import AppConfig
from app.core.enums import PaymentGatewayType
from app.core.exceptions import NotFoundError, PaymentGatewayError, ValidationError
from app.modules.gateways.api.schemas import (
    GatewayCatalogEntryResponse,
    GatewayCatalogResponse,
    GatewayFieldSpecResponse,
    GatewayResponse,
    GatewayTestPaymentResponse,
    GatewayTestPaymentStatusResponse,
    ReorderGatewaysRequest,
    UpdateGatewaySettingsRequest,
)
from app.modules.gateways.dto import (
    PaymentGatewayDto,
    ReorderGatewaysDto,
    UpdateGatewaySettingsDto,
)
from app.modules.gateways.field_catalog import GATEWAY_FIELD_CATALOG
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    ToggleGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)
from app.modules.payments import CreateTestPaymentUseCase, GetTestPaymentStatusUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/gateways", tags=["gateways"])


def _to_response(gateway: PaymentGatewayDto) -> GatewayResponse:
    return GatewayResponse(
        type=gateway.type,
        order_index=gateway.order_index,
        is_active=gateway.is_active,
        is_configured=gateway.is_configured,
    )


@router.get("", response_model=list[GatewayResponse])
@inject
async def list_gateways(
    use_case: FromDishka[ListGatewaysUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[GatewayResponse]:
    gateways = await use_case(actor)
    return [_to_response(gateway) for gateway in gateways]


@router.get("/catalog", response_model=GatewayCatalogResponse)
@inject
async def get_gateway_catalog(
    config: FromDishka[AppConfig],
    actor: UserDto = Depends(require_admin),
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


@router.put("/{gateway_type}/settings", response_model=GatewayResponse)
@inject
async def update_gateway_settings(
    gateway_type: PaymentGatewayType,
    payload: UpdateGatewaySettingsRequest,
    use_case: FromDishka[UpdateGatewaySettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> GatewayResponse:
    try:
        gateway = await use_case(
            actor, UpdateGatewaySettingsDto(type=gateway_type, values=payload.values)
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(gateway)


@router.post("/{gateway_type}/toggle", response_model=GatewayResponse)
@inject
async def toggle_gateway_active(
    gateway_type: PaymentGatewayType,
    use_case: FromDishka[ToggleGatewayActiveUseCase],
    actor: UserDto = Depends(require_admin),
) -> GatewayResponse:
    try:
        gateway = await use_case(actor, gateway_type)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(gateway)


@router.post("/{gateway_type}/test", response_model=GatewayTestPaymentResponse)
@inject
async def create_test_payment(
    gateway_type: PaymentGatewayType,
    use_case: FromDishka[CreateTestPaymentUseCase],
    actor: UserDto = Depends(require_admin),
) -> GatewayTestPaymentResponse:
    try:
        result = await use_case(actor, gateway_type)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except PaymentGatewayError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return GatewayTestPaymentResponse(
        order_id=result.order_id, confirmation_url=result.confirmation_url
    )


@router.get("/test-payments/{order_id}", response_model=GatewayTestPaymentStatusResponse)
@inject
async def get_test_payment_status(
    order_id: int,
    use_case: FromDishka[GetTestPaymentStatusUseCase],
    actor: UserDto = Depends(require_admin),
) -> GatewayTestPaymentStatusResponse:
    try:
        order_status = await use_case(actor, order_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return GatewayTestPaymentStatusResponse(status=order_status)


@router.put("/order", response_model=list[GatewayResponse])
@inject
async def reorder_gateways(
    payload: ReorderGatewaysRequest,
    use_case: FromDishka[ReorderGatewaysUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[GatewayResponse]:
    try:
        gateways = await use_case(actor, ReorderGatewaysDto(ordered_types=payload.types))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return [_to_response(gateway) for gateway in gateways]
