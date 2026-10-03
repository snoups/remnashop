from dataclasses import asdict
from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import PaymentGatewayType, PurchaseType, TransactionStatus
from app.modules.transactions.api.schemas import (
    CreateTestPaymentRequest,
    TestPaymentResponse,
    TestPaymentStatusResponse,
    TransactionGatewayListResponse,
    TransactionPageResponse,
    TransactionResponse,
    TransactionSummaryResponse,
    TransactionUserResponse,
)
from app.modules.transactions.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    GetTransactionSummaryDto,
    ListTransactionsDto,
    TransactionWithUserDto,
)
from app.modules.transactions.usecases import (
    CreateTestPaymentUseCase,
    FulfillTransactionUseCase,
    GetTestPaymentStatusUseCase,
    GetTransactionSummaryUseCase,
    GetTransactionUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _to_response(item: TransactionWithUserDto) -> TransactionResponse:
    order, user = item.order, item.user
    return TransactionResponse(
        id=order.id,
        user_id=order.user_id,
        user=TransactionUserResponse.model_validate(user, from_attributes=True)
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
        fulfilled_subscription_id=order.fulfilled_subscription_id,
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
        ListTransactionsDto(
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
        GetTransactionSummaryDto(
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


@router.post(
    "/test-payments",
    status_code=status.HTTP_201_CREATED,
    response_model=TestPaymentResponse,
    responses=error_responses(400, 502),
)
@inject
async def create_test_payment(
    payload: CreateTestPaymentRequest,
    use_case: FromDishka[CreateTestPaymentUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> TestPaymentResponse:
    result = await use_case(actor, payload.gateway_type)
    return TestPaymentResponse.model_validate(result, from_attributes=True)


@router.get(
    "/test-payments/{order_id:int}",
    response_model=TestPaymentStatusResponse,
    responses=error_responses(404),
)
@inject
async def get_test_payment_status(
    order_id: int,
    use_case: FromDishka[GetTestPaymentStatusUseCase],
    actor: Actor = Depends(require_admin),
) -> TestPaymentStatusResponse:
    return TestPaymentStatusResponse(status=await use_case(actor, order_id))


@router.get(
    "/{transaction_id:int}", response_model=TransactionResponse, responses=error_responses(404)
)
@inject
async def get_transaction(
    transaction_id: int,
    use_case: FromDishka[GetTransactionUseCase],
    actor: Actor = Depends(require_admin),
) -> TransactionResponse:
    item = await use_case(actor, transaction_id)
    return _to_response(item)


@router.post(
    "/{transaction_id:int}/actions/fulfill",
    response_model=TransactionResponse,
    responses=error_responses(404, 409),
)
@inject
async def fulfill_transaction(
    transaction_id: int,
    use_case: FromDishka[FulfillTransactionUseCase],
    actor: Actor = Depends(require_admin),
) -> TransactionResponse:
    item = await use_case(actor, transaction_id)
    return _to_response(item)
