from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, INT32_MAX, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.utils.http import resolve_client_ip
from app.modules.transactions.api.schemas import ManageRecurringPaymentRequest
from app.modules.transactions.recurring_admin import (
    ListRecurringPaymentsDto,
    ManageRecurringPaymentDto,
    RecurringAction,
    RecurringPaymentAdminPage,
)
from app.modules.transactions.recurring_policy import RecurringState
from app.modules.transactions.usecases.list_recurring_payments import ListRecurringPaymentsUseCase
from app.modules.transactions.usecases.manage_recurring_payment import ManageRecurringPaymentUseCase

router = APIRouter()


@router.get("/recurring", response_model=RecurringPaymentAdminPage, responses=error_responses(403))
@inject
async def list_recurring_payments(
    use_case: FromDishka[ListRecurringPaymentsUseCase],
    actor: Actor = Depends(require_admin),
    state: Optional[RecurringState] = None,
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> RecurringPaymentAdminPage:
    return await use_case(
        actor, ListRecurringPaymentsDto(state=state, search=search, page=page, page_size=page_size)
    )


@router.post(
    "/recurring/{subscription_id:int}/actions/{action}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 403, 404, 409, 502),
)
@inject
async def manage_recurring_payment(
    action: RecurringAction,
    data: ManageRecurringPaymentRequest,
    request: Request,
    use_case: FromDishka[ManageRecurringPaymentUseCase],
    subscription_id: int = Path(ge=1, le=INT32_MAX),
    actor: Actor = Depends(require_admin),
) -> Response:
    await use_case(
        actor,
        ManageRecurringPaymentDto(
            subscription_id=subscription_id,
            action=action,
            expected_pending_transaction_id=data.expected_pending_transaction_id,
            client_ip=resolve_client_ip(request),
        ),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
