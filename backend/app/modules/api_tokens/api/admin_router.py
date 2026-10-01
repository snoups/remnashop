from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.api_tokens.api.schemas import (
    ApiTokenListResponse,
    ApiTokenResponse,
    CreateApiTokenRequest,
    CreatedApiTokenResponse,
)
from app.modules.api_tokens.dto import ApiTokenDto
from app.modules.api_tokens.usecases import (
    CreateApiTokenInput,
    CreateApiTokenUseCase,
    ListApiTokensUseCase,
    RevokeApiTokenUseCase,
)

router = APIRouter(prefix="/api-tokens", tags=["api-tokens"])


def _to_response(token: ApiTokenDto) -> ApiTokenResponse:
    return ApiTokenResponse(
        id=token.id,
        name=token.name,
        permissions=token.permissions,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        expires_at=token.expires_at,
    )


@router.get("", response_model=ApiTokenListResponse)
@inject
async def list_api_tokens(
    use_case: FromDishka[ListApiTokensUseCase],
    actor: Actor = Depends(require_admin),
) -> ApiTokenListResponse:
    tokens = await use_case(actor)
    items = [_to_response(token) for token in tokens]
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
    use_case: FromDishka[CreateApiTokenUseCase],
    actor: Actor = Depends(require_admin),
) -> CreatedApiTokenResponse:
    result = await use_case(
        actor,
        CreateApiTokenInput(
            name=payload.name,
            permissions=payload.permissions,
            expires_in_days=payload.expires_in_days,
        ),
    )
    return CreatedApiTokenResponse(token=_to_response(result.token), secret=result.secret)


@router.delete(
    "/{token_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def revoke_api_token(
    token_id: int,
    use_case: FromDishka[RevokeApiTokenUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, token_id)
