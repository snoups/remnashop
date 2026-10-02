from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies.admin import require_admin_user
from app.api.errors import error_responses
from app.core.exceptions import AuthenticationError, ValidationError
from app.modules.passkeys.api.schemas import (
    PasskeyListResponse,
    PasskeyResponse,
    RenamePasskeyRequest,
    VerifyPasskeyRegistrationRequest,
)
from app.modules.passkeys.dto import (
    RenamePasskeyDto,
    VerifyPasskeyRegistrationDto,
)
from app.modules.passkeys.usecases import (
    DeletePasskeyUseCase,
    GetPasskeyRegistrationOptionsUseCase,
    ListPasskeysUseCase,
    RenamePasskeyUseCase,
    VerifyPasskeyRegistrationUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/auth/passkeys", tags=["auth"])


@router.get("", response_model=PasskeyListResponse)
@inject
async def list_passkeys(
    use_case: FromDishka[ListPasskeysUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> PasskeyListResponse:
    passkeys = await use_case(actor)
    items = [PasskeyResponse.model_validate(passkey, from_attributes=True) for passkey in passkeys]
    return PasskeyListResponse(items=items, total=len(items))


@router.get("/register/options", responses=error_responses(400))
@inject
async def get_registration_options(
    use_case: FromDishka[GetPasskeyRegistrationOptionsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> Response:
    try:
        options_json = await use_case(actor)
    except AuthenticationError as error:
        raise ValidationError(str(error), code=error.code) from error
    return Response(content=options_json, media_type="application/json")


@router.post("/register/verify", response_model=PasskeyResponse, responses=error_responses(400))
@inject
async def verify_registration(
    payload: VerifyPasskeyRegistrationRequest,
    use_case: FromDishka[VerifyPasskeyRegistrationUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> PasskeyResponse:
    try:
        created = await use_case(
            actor,
            VerifyPasskeyRegistrationDto(credential=payload.credential, name=payload.name),
        )
    except AuthenticationError as error:
        raise ValidationError(str(error), code=error.code) from error
    return PasskeyResponse.model_validate(created, from_attributes=True)


@router.patch("/{passkey_id}", response_model=PasskeyResponse, responses=error_responses(404))
@inject
async def rename_passkey(
    passkey_id: int,
    payload: RenamePasskeyRequest,
    use_case: FromDishka[RenamePasskeyUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> PasskeyResponse:
    renamed = await use_case(actor, RenamePasskeyDto(id=passkey_id, name=payload.name))
    return PasskeyResponse.model_validate(renamed, from_attributes=True)


@router.delete(
    "/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_passkey(
    passkey_id: int,
    use_case: FromDishka[DeletePasskeyUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor, passkey_id)
