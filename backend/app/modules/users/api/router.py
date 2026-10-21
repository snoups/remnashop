from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies.public import (
    AuthContext,
    get_auth_context,
    get_current_session_id,
    get_profile_user,
)
from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import error_responses
from app.core.constants import TIME_1M
from app.core.enums import SessionAudience
from app.core.exceptions import PermissionDeniedError
from app.core.utils.http import resolve_client_ip
from app.modules.users.api.schemas import UpdateOwnProfileRequest
from app.modules.users.dto import UpdateOwnProfileDto, UserDto
from app.modules.users.schemas import CurrentUserResponse, to_current_user_response
from app.modules.users.usecases import (
    GetCurrentUserUseCase,
    UnsubscribeMarketingUseCase,
    UpdateOwnProfileUseCase,
)

# RFC 8058 one-click POSTs arrive from a few shared mail-provider IPs; the token is an HMAC
_UNSUBSCRIBE_LIMIT_PER_MINUTE: Final[int] = 600

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=CurrentUserResponse)
@inject
async def get_me(
    use_case: FromDishka[GetCurrentUserUseCase],
    actor: UserDto = Depends(get_profile_user),
) -> CurrentUserResponse:
    current_user = await use_case(actor)
    return to_current_user_response(current_user)


@router.patch("/users/me", response_model=CurrentUserResponse, responses=error_responses(400))
@inject
async def update_me(
    payload: UpdateOwnProfileRequest,
    request: Request,
    use_case: FromDishka[UpdateOwnProfileUseCase],
    actor: UserDto = Depends(get_profile_user),
    session_id: int = Depends(get_current_session_id),
    auth: AuthContext = Depends(get_auth_context),
) -> CurrentUserResponse:
    if (
        payload.new_password is not None or payload.current_password is not None
    ) and auth.audience is SessionAudience.CABINET:
        # dashboard credentials stay out of reach of the cabinet's domain
        raise PermissionDeniedError("Password change is not available")
    updated = await use_case(
        actor,
        UpdateOwnProfileDto(
            name=payload.name,
            current_password=payload.current_password,
            new_password=payload.new_password,
            language=payload.language,
            current_session_id=session_id,
            client_ip=resolve_client_ip(request),
        ),
    )
    return to_current_user_response(updated)


# POST only: mail scanners open links, and RFC 8058 clients POST here themselves
@router.post(
    "/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(
            rate_limit(
                key="cabinet_unsubscribe",
                limit=_UNSUBSCRIBE_LIMIT_PER_MINUTE,
                window_seconds=TIME_1M,
            )
        )
    ],
    responses=error_responses(400),
)
@inject
async def unsubscribe_marketing(
    use_case: FromDishka[UnsubscribeMarketingUseCase],
    token: str = Query(..., max_length=128),
) -> None:
    await use_case.execute(token)
