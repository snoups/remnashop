from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.modules.transactions.recurring_admin import (
    ListRecurringPaymentsDto,
    RecurringPaymentAdminPage,
    RecurringState,
)
from app.modules.transactions.usecases.list_recurring_payments import ListRecurringPaymentsUseCase

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
