from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import LegalDocumentKind, Locale, PurchaseChannel
from app.core.utils.http import resolve_client_ip
from app.modules.legal.api.schemas import (
    LegalAcceptanceResponse,
    LegalAcceptancesResponse,
    LegalDocumentItemResponse,
    LegalDocumentResponse,
    LegalDocumentsResponse,
    LegalTemplateResponse,
    LegalTextRequest,
    LegalTextResponse,
    UpdateLegalDocumentRequest,
)
from app.modules.legal.dto import LegalTextKeyDto, SetLegalTextDto, UpdateLegalDocumentDto
from app.modules.legal.usecases import (
    ListLegalDocumentsUseCase,
    ListUserLegalAcceptancesUseCase,
    RemoveLegalTextUseCase,
    SetLegalTextUseCase,
    UpdateLegalDocumentUseCase,
)

router = APIRouter(prefix="/legal-documents", tags=["legal-documents"])
user_router = APIRouter(prefix="/users", tags=["legal-documents"])


@router.get("", response_model=LegalDocumentsResponse)
@inject
async def list_legal_documents(
    use_case: FromDishka[ListLegalDocumentsUseCase],
    actor: Actor = Depends(require_admin),
) -> LegalDocumentsResponse:
    result = await use_case(actor)
    items = [
        LegalDocumentItemResponse(
            **LegalDocumentResponse.model_validate(document, from_attributes=True).model_dump(),
            texts=[
                LegalTextResponse.model_validate(text, from_attributes=True)
                for text in result.texts
                if text.kind == document.kind
            ],
            templates=[
                LegalTemplateResponse.model_validate(template, from_attributes=True)
                for template in result.templates
                if template.kind == document.kind
            ],
        )
        for document in result.documents
    ]
    return LegalDocumentsResponse(
        items=items,
        total=len(items),
        locales=result.locales,
    )


@router.patch("/{kind}", response_model=LegalDocumentResponse)
@inject
async def update_legal_document(
    kind: LegalDocumentKind,
    payload: UpdateLegalDocumentRequest,
    request: Request,
    use_case: FromDishka[UpdateLegalDocumentUseCase],
    actor: Actor = Depends(require_admin),
) -> LegalDocumentResponse:
    document = await use_case(
        actor,
        UpdateLegalDocumentDto(
            kind=kind,
            show_in_bot=payload.show_in_bot,
            show_in_cabinet=payload.show_in_cabinet,
            client_ip=resolve_client_ip(request),
        ),
    )
    return LegalDocumentResponse.model_validate(document, from_attributes=True)


@router.put("/{kind}/{locale}", response_model=LegalTextResponse, responses=error_responses(400))
@inject
async def set_legal_text(
    kind: LegalDocumentKind,
    locale: Locale,
    payload: LegalTextRequest,
    request: Request,
    use_case: FromDishka[SetLegalTextUseCase],
    channel: Optional[PurchaseChannel] = None,
    actor: Actor = Depends(require_admin),
) -> LegalTextResponse:
    revision = await use_case(
        actor,
        SetLegalTextDto(
            kind=kind,
            locale=locale,
            channel=channel,
            title=payload.title,
            body=payload.body,
            requires_reacceptance=payload.requires_reacceptance,
            client_ip=resolve_client_ip(request),
        ),
    )
    return LegalTextResponse.model_validate(revision, from_attributes=True)


@router.delete(
    "/{kind}/{locale}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def remove_legal_text(
    kind: LegalDocumentKind,
    locale: Locale,
    request: Request,
    use_case: FromDishka[RemoveLegalTextUseCase],
    channel: Optional[PurchaseChannel] = None,
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(
        actor,
        LegalTextKeyDto(
            kind=kind, locale=locale, channel=channel, client_ip=resolve_client_ip(request)
        ),
    )


@user_router.get(
    "/{user_id:int}/legal-acceptances",
    response_model=LegalAcceptancesResponse,
    responses=error_responses(404),
)
@inject
async def list_user_legal_acceptances(
    user_id: int,
    use_case: FromDishka[ListUserLegalAcceptancesUseCase],
    actor: Actor = Depends(require_admin),
) -> LegalAcceptancesResponse:
    acceptances = await use_case(actor, user_id)
    return LegalAcceptancesResponse(
        items=[
            LegalAcceptanceResponse.model_validate(item, from_attributes=True)
            for item in acceptances
        ],
        total=len(acceptances),
    )
