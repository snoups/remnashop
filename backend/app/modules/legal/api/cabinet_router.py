from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request

from app.api.dependencies.public import get_cabinet_user
from app.api.dependencies.rate_limit import user_rate_limit
from app.core.constants import TIME_1M
from app.core.enums import Locale, PurchaseChannel
from app.core.utils.http import resolve_client_ip
from app.modules.legal.api.schemas import (
    AcceptLegalRequest,
    PendingLegalDocumentResponse,
    PendingLegalResponse,
)
from app.modules.legal.dto import AcceptLegalDocumentsDto, PendingLegalDocumentsDto
from app.modules.legal.usecases import (
    AcceptLegalDocumentsUseCase,
    GetPendingLegalDocumentsUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/cabinet/legal", tags=["legal"])


def _locale(value: str) -> Optional[Locale]:
    # a stale cabinet may send a language that is no longer served
    try:
        return Locale(value)
    except ValueError:
        return None


def _response(pending: PendingLegalDocumentsDto) -> PendingLegalResponse:
    return PendingLegalResponse(
        items=[
            PendingLegalDocumentResponse.model_validate(document, from_attributes=True)
            for document in pending.documents
        ],
        total=len(pending.documents),
        is_update=pending.is_update,
    )


@router.get(
    "/pending",
    response_model=PendingLegalResponse,
    dependencies=[Depends(user_rate_limit(key="legal_pending", limit=30, window_seconds=TIME_1M))],
)
@inject
async def list_pending_legal_documents(
    use_case: FromDishka[GetPendingLegalDocumentsUseCase],
    locale: str = "",
    user: UserDto = Depends(get_cabinet_user),
) -> PendingLegalResponse:
    return _response(await use_case.execute(user, PurchaseChannel.CABINET, _locale(locale)))


@router.post(
    "/actions/accept",
    response_model=PendingLegalResponse,
    dependencies=[Depends(user_rate_limit(key="legal_accept", limit=30, window_seconds=TIME_1M))],
)
@inject
async def accept_legal_documents(
    payload: AcceptLegalRequest,
    request: Request,
    use_case: FromDishka[AcceptLegalDocumentsUseCase],
    user: UserDto = Depends(get_cabinet_user),
) -> PendingLegalResponse:
    pending = await use_case.execute(
        AcceptLegalDocumentsDto(
            user=user,
            channel=PurchaseChannel.CABINET,
            locale=_locale(payload.locale),
            revision_ids=payload.revision_ids,
            client_ip=resolve_client_ip(request),
        )
    )
    return _response(pending)
