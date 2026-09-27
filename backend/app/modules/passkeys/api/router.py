from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.dependencies.rate_limit import rate_limit
from app.core.config import AppConfig
from app.core.constants import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, TIME_1M
from app.core.exceptions import AuthenticationError
from app.core.utils.http import resolve_client_ip
from app.core.utils.time import datetime_now
from app.modules.auth.api.schemas import AuthResponse
from app.modules.auth.session_issuer import IssuedSession
from app.modules.passkeys.api.schemas import VerifyPasskeyAuthenticationRequest
from app.modules.passkeys.usecases import (
    GetPasskeyAuthenticationOptionsUseCase,
    VerifyPasskeyAuthenticationUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/auth/passkeys", tags=["auth"])


def _set_session_cookies(response: Response, issued: IssuedSession, secure: bool) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        issued.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=int((issued.expires_at - datetime_now()).total_seconds()),
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        issued.csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=int((issued.expires_at - datetime_now()).total_seconds()),
    )


def _to_auth_response(user: UserDto, access_token: str) -> AuthResponse:
    assert user.login is not None
    return AuthResponse(
        id=user.id, login=user.login, role=str(user.role), access_token=access_token
    )


@router.get(
    "/authenticate/options",
    dependencies=[
        Depends(rate_limit(key="passkey_authenticate", limit=10, window_seconds=TIME_1M))
    ],
)
@inject
async def get_authentication_options(
    use_case: FromDishka[GetPasskeyAuthenticationOptionsUseCase],
) -> Response:
    try:
        options_json = await use_case.execute()
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return Response(content=options_json, media_type="application/json")


@router.post(
    "/authenticate/verify",
    response_model=AuthResponse,
    dependencies=[
        Depends(rate_limit(key="passkey_authenticate", limit=10, window_seconds=TIME_1M))
    ],
)
@inject
async def verify_authentication(
    payload: VerifyPasskeyAuthenticationRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[VerifyPasskeyAuthenticationUseCase],
    config: FromDishka[AppConfig],
) -> AuthResponse:
    try:
        user, issued = await use_case.execute(
            credential=payload.credential,
            client_ip=resolve_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    _set_session_cookies(response, issued, config.secure_cookies)
    return _to_auth_response(user, issued.access_token)
