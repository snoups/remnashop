from dataclasses import asdict
from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import PaymentGatewayType, PurchaseType, TransactionStatus
from app.modules.transactions.api.schemas import (
    TransactionGatewayListResponse,
    TransactionPageResponse,
    TransactionResponse,
    TransactionSummaryResponse,
    TransactionUserResponse,
)
from app.modules.transactions.dto import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, TransactionWithUserDto
from app.modules.transactions.usecases import (
    GetTransactionSummaryInput,
    GetTransactionSummaryUseCase,
    GetTransactionUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsInput,
    ListTransactionsUseCase,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _to_response(item: TransactionWithUserDto) -> TransactionResponse:
    order, user = item.order, item.user
    return TransactionResponse(
        id=order.id,
        user_id=order.user_id,
        user=TransactionUserResponse(
            name=user.name,
            username=user.username,
            telegram_id=user.telegram_id,
            email=user.email,
        )
        if user is not None
        else None,
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


@router.get("", response_model=TransactionPageResponse)
@inject
async def list_transactions(
    use_case: FromDishka[ListTransactionsUseCase],
    actor: Actor = Depends(require_admin),
    status_filter: Optional[TransactionStatus] = Query(None, alias="status"),
    gateway_type: Optional[PaymentGatewayType] = None,
    purchase_type: Optional[PurchaseType] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> TransactionPageResponse:
    items, total = await use_case(
        actor,
        ListTransactionsInput(
            status=status_filter,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=created_from,
            created_to=created_to,
            search=search,
            user_id=user_id,
            page=page,
            page_size=page_size,
        ),
    )
    return TransactionPageResponse(items=[_to_response(item) for item in items], total=total)


# declared before /{order_id} so "summary"/"gateways" aren't parsed as an order id
@router.get("/summary", response_model=TransactionSummaryResponse)
@inject
async def get_transaction_summary(
    use_case: FromDishka[GetTransactionSummaryUseCase],
    actor: Actor = Depends(require_admin),
    status_filter: Optional[TransactionStatus] = Query(None, alias="status"),
    gateway_type: Optional[PaymentGatewayType] = None,
    purchase_type: Optional[PurchaseType] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
) -> TransactionSummaryResponse:
    summary = await use_case(
        actor,
        GetTransactionSummaryInput(
            status=status_filter,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=created_from,
            created_to=created_to,
            search=search,
            user_id=user_id,
        ),
    )
    return TransactionSummaryResponse(**asdict(summary))


@router.get("/gateways", response_model=TransactionGatewayListResponse)
@inject
async def list_transaction_gateways(
    use_case: FromDishka[ListTransactionGatewaysUseCase],
    actor: Actor = Depends(require_admin),
) -> TransactionGatewayListResponse:
    items = await use_case(actor, None)
    return TransactionGatewayListResponse(items=items, total=len(items))


@router.get("/{transaction_id}", response_model=TransactionResponse, responses=error_responses(404))
@inject
async def get_transaction(
    transaction_id: int,
    use_case: FromDishka[GetTransactionUseCase],
    actor: Actor = Depends(require_admin),
) -> TransactionResponse:
    item = await use_case(actor, transaction_id)
    return _to_response(item)
