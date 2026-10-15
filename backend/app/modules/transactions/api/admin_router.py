from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.enums import PaymentGatewayType, PurchaseType, TransactionStatus
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.transactions.api.schemas import (
    CreateTestPaymentRequest,
    PaymentWaitlistCountResponse,
    TestPaymentResponse,
    TestPaymentStatusResponse,
    TransactionGatewayListResponse,
    TransactionPageResponse,
    TransactionResponse,
    TransactionSummaryResponse,
)
from app.modules.transactions.dto import (
    GetTransactionSummaryDto,
    ListTransactionsDto,
    TransactionWithUserDto,
)
from app.modules.transactions.usecases import (
    CreateTestPaymentUseCase,
    FulfillTransactionUseCase,
    GetPaymentWaitlistCountUseCase,
    GetTestPaymentStatusUseCase,
    GetTransactionSummaryUseCase,
    GetTransactionUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _to_response(item: TransactionWithUserDto) -> TransactionResponse:
    return TransactionResponse.model_validate(
        {**dict(item.order), "user": item.user}, from_attributes=True
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
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
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
            created_from=range_start_utc(created_from),
            created_to=range_end_utc(created_to),
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
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
    user_id: Optional[int] = None,
) -> TransactionSummaryResponse:
    summary = await use_case(
        actor,
        GetTransactionSummaryDto(
            status=status_filter,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=range_start_utc(created_from),
            created_to=range_end_utc(created_to),
            search=search,
            user_id=user_id,
        ),
    )
    return TransactionSummaryResponse.model_validate(summary, from_attributes=True)


@router.get("/waitlist", response_model=PaymentWaitlistCountResponse)
@inject
async def get_payment_waitlist_count(
    use_case: FromDishka[GetPaymentWaitlistCountUseCase],
    actor: Actor = Depends(require_admin),
) -> PaymentWaitlistCountResponse:
    return PaymentWaitlistCountResponse.model_validate(await use_case(actor), from_attributes=True)


@router.get("/gateways", response_model=TransactionGatewayListResponse)
@inject
async def list_transaction_gateways(
    use_case: FromDishka[ListTransactionGatewaysUseCase],
    actor: Actor = Depends(require_admin),
) -> TransactionGatewayListResponse:
    items = await use_case(actor)
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
