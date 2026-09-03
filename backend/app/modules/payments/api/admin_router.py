from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.admin import require_admin
from app.core.enums import PaymentOrderStatus
from app.core.exceptions import NotFoundError
from app.modules.payments.api.schemas import PaymentOrderPageResponse, PaymentOrderResponse
from app.modules.payments.dto import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PaymentOrderDto
from app.modules.payments.usecases import (
    GetPaymentOrderUseCase,
    ListPaymentOrdersInput,
    ListPaymentOrdersUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/payments/orders", tags=["payments"])


def _to_response(order: PaymentOrderDto) -> PaymentOrderResponse:
    return PaymentOrderResponse(
        id=order.id,
        user_id=order.user_id,
        plan_id=order.plan_id,
        plan_snapshot=order.plan_snapshot.to_json(),
        duration_days=order.duration_days,
        currency=order.currency.value,
        purchase_type=order.purchase_type.value,
        target_subscription_id=order.target_subscription_id,
        gateway_type=order.gateway_type.value,
        external_payment_id=order.external_payment_id,
        status=order.status.value,
        base_price=order.base_price,
        discount_percent=order.discount_percent,
        discount_source=order.discount_source.value,
        final_price=order.final_price,
        customer_email=order.customer_email,
        idempotency_key=order.idempotency_key,
        expires_at=order.expires_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get("", response_model=PaymentOrderPageResponse)
@inject
async def list_payment_orders(
    use_case: FromDishka[ListPaymentOrdersUseCase],
    actor: UserDto = Depends(require_admin),
    status_filter: Optional[PaymentOrderStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaymentOrderPageResponse:
    orders, total = await use_case(
        actor, ListPaymentOrdersInput(status=status_filter, page=page, page_size=page_size)
    )
    return PaymentOrderPageResponse(items=[_to_response(order) for order in orders], total=total)


@router.get("/{order_id}", response_model=PaymentOrderResponse)
@inject
async def get_payment_order(
    order_id: int,
    use_case: FromDishka[GetPaymentOrderUseCase],
    actor: UserDto = Depends(require_admin),
) -> PaymentOrderResponse:
    try:
        order = await use_case(actor, order_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_response(order)
