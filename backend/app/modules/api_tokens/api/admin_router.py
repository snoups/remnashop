from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.utils.http import resolve_client_ip
from app.modules.api_tokens.api.schemas import (
    ApiTokenListResponse,
    ApiTokenResponse,
    CreateApiTokenRequest,
    CreatedApiTokenResponse,
    DocsOttResponse,
)
from app.modules.api_tokens.dto import IssueApiTokenDto, RevokeApiTokenDto
from app.modules.api_tokens.usecases import (
    CreateApiTokenUseCase,
    IssueDocsOttUseCase,
    ListApiTokensUseCase,
    RevokeApiTokenUseCase,
)

router = APIRouter(prefix="/api-tokens", tags=["api-tokens"])


@router.get("", response_model=ApiTokenListResponse)
@inject
async def list_api_tokens(
    use_case: FromDishka[ListApiTokensUseCase],
    actor: Actor = Depends(require_admin),
) -> ApiTokenListResponse:
    tokens = await use_case(actor)
    items = [ApiTokenResponse.model_validate(token, from_attributes=True) for token in tokens]
    return ApiTokenListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=CreatedApiTokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400),
)
@inject
async def create_api_token(
    payload: CreateApiTokenRequest,
    request: Request,
    use_case: FromDishka[CreateApiTokenUseCase],
    actor: Actor = Depends(require_admin),
) -> CreatedApiTokenResponse:
    result = await use_case(
        actor,
        IssueApiTokenDto(
            name=payload.name,
            scopes=payload.scopes,
            expires_in_days=payload.expires_in_days,
            ip_allowlist=payload.ip_allowlist,
            client_ip=resolve_client_ip(request),
        ),
    )
    return CreatedApiTokenResponse.model_validate(result, from_attributes=True)


@router.post("/actions/issue-ott", response_model=DocsOttResponse)
@inject
async def issue_docs_ott(
    use_case: FromDishka[IssueDocsOttUseCase],
    actor: Actor = Depends(require_admin),
) -> DocsOttResponse:
    return DocsOttResponse(ott=await use_case(actor))


@router.delete(
    "/{token_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def revoke_api_token(
    token_id: int,
    request: Request,
    use_case: FromDishka[RevokeApiTokenUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(
        actor, RevokeApiTokenDto(token_id=token_id, client_ip=resolve_client_ip(request))
    )
