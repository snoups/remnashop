from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import error_responses
from app.core.config import AppConfig
from app.core.constants import TIME_1M
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import AuthResponse, set_session_cookies, to_auth_response
from app.modules.passkeys.api.schemas import VerifyPasskeyAuthenticationRequest
from app.modules.passkeys.usecases import (
    GetPasskeyAuthenticationOptionsUseCase,
    VerifyPasskeyAuthenticationUseCase,
)

router = APIRouter(prefix="/auth/passkeys", tags=["auth"])


@router.get(
    "/authenticate/options",
    dependencies=[
        Depends(rate_limit(key="passkey_authenticate", limit=10, window_seconds=TIME_1M))
    ],
    responses=error_responses(400),
)
@inject
async def get_authentication_options(
    use_case: FromDishka[GetPasskeyAuthenticationOptionsUseCase],
) -> Response:
    try:
        options_json = await use_case.execute()
    except AuthenticationError as error:
        raise ValidationError(str(error), code=error.code) from error
    return Response(content=options_json, media_type="application/json")


@router.post(
    "/authenticate/verify",
    response_model=AuthResponse,
    dependencies=[
        Depends(rate_limit(key="passkey_authenticate", limit=10, window_seconds=TIME_1M))
    ],
    responses=error_responses(401),
)
@inject
async def verify_authentication(
    payload: VerifyPasskeyAuthenticationRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[VerifyPasskeyAuthenticationUseCase],
    config: FromDishka[AppConfig],
) -> AuthResponse:
    user, issued = await use_case.execute(
        credential=payload.credential,
        client_ip=resolve_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    set_session_cookies(response, issued, config.secure_cookies)
    return to_auth_response(user, issued.access_token)
