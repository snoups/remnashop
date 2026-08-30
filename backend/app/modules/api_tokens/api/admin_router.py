from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.api_tokens.api.schemas import (
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
from app.modules.users import UserDto

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


@router.get("", response_model=list[ApiTokenResponse])
@inject
async def list_api_tokens(
    use_case: FromDishka[ListApiTokensUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[ApiTokenResponse]:
    tokens = await use_case(actor)
    return [_to_response(token) for token in tokens]


@router.post("", response_model=CreatedApiTokenResponse)
@inject
async def create_api_token(
    payload: CreateApiTokenRequest,
    use_case: FromDishka[CreateApiTokenUseCase],
    actor: UserDto = Depends(require_admin),
) -> CreatedApiTokenResponse:
    try:
        result = await use_case(
            actor,
            CreateApiTokenInput(
                name=payload.name,
                permissions=payload.permissions,
                expires_in_days=payload.expires_in_days,
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return CreatedApiTokenResponse(token=_to_response(result.token), secret=result.secret)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def revoke_api_token(
    token_id: int,
    use_case: FromDishka[RevokeApiTokenUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, token_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
