from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies.public import AuthContext, get_auth_context, get_current_user
from app.api.errors import error_responses
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.enums import PurchaseChannel, SessionAudience
from app.core.utils.http import resolve_client_ip
from app.modules.transactions.api.schemas import (
    CheckoutQuoteResponse,
    CheckoutResponse,
    CreateCheckoutRequest,
    OwnTransactionListResponse,
    OwnTransactionResponse,
    PaymentMethodListResponse,
    PaymentMethodResponse,
    QuoteCheckoutRequest,
)
from app.modules.transactions.dto import (
    CreateCheckoutDto,
    ListOwnTransactionsDto,
    QuoteCheckoutDto,
)
from app.modules.transactions.usecases import (
    CreateCheckoutUseCase,
    GetOwnTransactionUseCase,
    ListOwnTransactionsUseCase,
    ListPaymentMethodsUseCase,
    QuoteCheckoutUseCase,
)
from app.modules.users import UserDto

router = APIRouter(tags=["transactions"])


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 403, 404, 502),
)
@inject
async def create_checkout(
    request: Request,
    payload: CreateCheckoutRequest,
    use_case: FromDishka[CreateCheckoutUseCase],
    actor: UserDto = Depends(get_current_user),
    auth: AuthContext = Depends(get_auth_context),
) -> CheckoutResponse:
    result = await use_case(
        actor,
        CreateCheckoutDto(
            plan_id=payload.plan_id,
            duration_days=payload.duration_days,
            currency=payload.currency,
            purchase_type=payload.purchase_type,
            channel=PurchaseChannel.CABINET,
            gateway_type=payload.gateway_type,
            target_subscription_id=payload.target_subscription_id,
            customer_email=payload.customer_email,
            plan_code=payload.plan_code,
            legal_locale=payload.legal_locale,
            client_ip=resolve_client_ip(request),
            return_to="cabinet" if auth.audience is SessionAudience.CABINET else "default",
        ),
    )
    return CheckoutResponse.model_validate(result, from_attributes=True)


@router.post(
    "/checkout/quote",
    response_model=CheckoutQuoteResponse,
    responses=error_responses(400, 404),
)
@inject
async def quote_checkout(
    payload: QuoteCheckoutRequest,
    use_case: FromDishka[QuoteCheckoutUseCase],
    actor: UserDto = Depends(get_current_user),
) -> CheckoutQuoteResponse:
    quote = await use_case(
        actor,
        QuoteCheckoutDto(
            plan_id=payload.plan_id,
            duration_days=payload.duration_days,
            currency=payload.currency,
            plan_code=payload.plan_code,
        ),
    )
    return CheckoutQuoteResponse(
        base_price=quote.base_price,
        plan_discount_percent=quote.plan_discount_percent,
        discount_percent=quote.discount_percent,
        discount_source=quote.discount_source,
        final_price=quote.final_price,
        currency=payload.currency,
    )


@router.get("/checkout/methods", response_model=PaymentMethodListResponse)
@inject
async def list_checkout_methods(
    use_case: FromDishka[ListPaymentMethodsUseCase],
    actor: UserDto = Depends(get_current_user),
) -> PaymentMethodListResponse:
    methods = await use_case(actor)
    items = [PaymentMethodResponse.model_validate(m, from_attributes=True) for m in methods]
    return PaymentMethodListResponse(items=items, total=len(items))


@router.get("/transactions/me", response_model=OwnTransactionListResponse)
@inject
async def list_own_transactions(
    use_case: FromDishka[ListOwnTransactionsUseCase],
    actor: UserDto = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> OwnTransactionListResponse:
    orders, total = await use_case(actor, ListOwnTransactionsDto(page=page, page_size=page_size))
    return OwnTransactionListResponse(
        items=[OwnTransactionResponse.from_dto(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/transactions/me/{transaction_id:int}",
    response_model=OwnTransactionResponse,
    responses=error_responses(404),
)
@inject
async def get_own_transaction(
    transaction_id: int,
    use_case: FromDishka[GetOwnTransactionUseCase],
    actor: UserDto = Depends(get_current_user),
) -> OwnTransactionResponse:
    return OwnTransactionResponse.from_dto(await use_case(actor, transaction_id))
