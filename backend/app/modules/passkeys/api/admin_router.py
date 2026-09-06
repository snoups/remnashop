from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import AuthenticationError, NotFoundError
from app.modules.passkeys.api.schemas import (
    PasskeyResponse,
    RenamePasskeyRequest,
    VerifyPasskeyRegistrationRequest,
)
from app.modules.passkeys.dto import (
    PasskeyCredentialDto,
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


def _to_response(passkey: PasskeyCredentialDto) -> PasskeyResponse:
    return PasskeyResponse(
        id=passkey.id,
        name=passkey.name or "Passkey",
        device_type=passkey.device_type,
        backed_up=passkey.backed_up,
        created_at=passkey.created_at,
        last_used_at=passkey.last_used_at,
    )


@router.get("", response_model=list[PasskeyResponse])
@inject
async def list_passkeys(
    use_case: FromDishka[ListPasskeysUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[PasskeyResponse]:
    passkeys = await use_case(actor)
    return [_to_response(passkey) for passkey in passkeys]


@router.get("/register/options")
@inject
async def get_registration_options(
    use_case: FromDishka[GetPasskeyRegistrationOptionsUseCase],
    actor: UserDto = Depends(require_admin),
) -> Response:
    try:
        options_json = await use_case(actor)
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return Response(content=options_json, media_type="application/json")


@router.post("/register/verify", response_model=PasskeyResponse)
@inject
async def verify_registration(
    payload: VerifyPasskeyRegistrationRequest,
    use_case: FromDishka[VerifyPasskeyRegistrationUseCase],
    actor: UserDto = Depends(require_admin),
) -> PasskeyResponse:
    try:
        created = await use_case(
            actor,
            VerifyPasskeyRegistrationDto(credential=payload.credential, name=payload.name),
        )
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(created)


@router.patch("/{passkey_id}", response_model=PasskeyResponse)
@inject
async def rename_passkey(
    passkey_id: int,
    payload: RenamePasskeyRequest,
    use_case: FromDishka[RenamePasskeyUseCase],
    actor: UserDto = Depends(require_admin),
) -> PasskeyResponse:
    try:
        renamed = await use_case(actor, RenamePasskeyDto(id=passkey_id, name=payload.name))
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_response(renamed)


@router.delete("/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_passkey(
    passkey_id: int,
    use_case: FromDishka[DeletePasskeyUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, passkey_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
