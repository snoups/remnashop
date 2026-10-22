from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limit import rate_limit
from app.core.constants import TIME_1M
from app.core.enums import Locale, PurchaseChannel
from app.modules.legal.api.schemas import LegalDocumentsPublicResponse, PublicLegalDocumentResponse
from app.modules.legal.usecases import ListVisibleLegalDocumentsUseCase

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get(
    "/documents",
    response_model=LegalDocumentsPublicResponse,
    dependencies=[Depends(rate_limit(key="legal_documents", limit=30, window_seconds=TIME_1M))],
)
@inject
async def list_public_legal_documents(
    use_case: FromDishka[ListVisibleLegalDocumentsUseCase],
    locale: str = "",
) -> LegalDocumentsPublicResponse:
    # a stale cabinet may send a language that is no longer served
    try:
        requested: Optional[Locale] = Locale(locale)
    except ValueError:
        requested = None
    documents = await use_case.execute(PurchaseChannel.CABINET, requested)
    return LegalDocumentsPublicResponse(
        items=[
            PublicLegalDocumentResponse.model_validate(document, from_attributes=True)
            for document in documents
        ],
        total=len(documents),
    )
