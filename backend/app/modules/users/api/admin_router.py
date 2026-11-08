from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.enums import Role
from app.core.security.permissions import ROLE_PERMISSIONS
from app.core.utils.http import resolve_client_ip
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.users.api.schemas import (
    AdminDetailResponse,
    AdminListResponse,
    AdminPromoteResponse,
    AdminResponse,
    AdminWithPasswordResponse,
    BindTelegramRequest,
    BlacklistMatchPageResponse,
    CreateAdminRequest,
    PromoteAdminRequest,
    SecurityResponse,
    SetDiscountRequest,
    SetTrialAvailabilityRequest,
    UnblockBlacklistMatchesResponse,
    UpdateAdminRequest,
    UpdateSecurityRequest,
    UserListStatsResponse,
    UserPageResponse,
    UserRegistrationResponse,
)
from app.modules.users.dto import (
    BindTelegramDto,
    BlacklistMatchOrigin,
    BlockUserDto,
    ClearEmailUndeliverableDto,
    CreateAdminDto,
    DeleteAdminDto,
    DeletedFilter,
    DeleteUserDto,
    DemoteAdminDto,
    GetUserListStatsDto,
    ListBlacklistMatchesDto,
    ListUsersDto,
    PromoteToAdminDto,
    SetUserDiscountDto,
    SetUserTrialAvailabilityDto,
    UnbindTelegramDto,
    UnblockBlacklistMatchesDto,
    UnblockUserDto,
    UpdateAdminDto,
    UpdateSecuritySettingsDto,
    UserDto,
    UserSort,
)
from app.modules.users.schemas import (
    UserListItemResponse,
    UserResponse,
    effective_permission_names,
)
from app.modules.users.usecases import (
    BindTelegramIdUseCase,
    BlockUserUseCase,
    ClearEmailUndeliverableUseCase,
    CreateAdminUseCase,
    DeleteAdminUseCase,
    DeleteUserUseCase,
    DemoteAdminUseCase,
    GetAdminUseCase,
    GetCurrentUserUseCase,
    GetUserListStatsUseCase,
    GetUserRegistrationUseCase,
    GetUserUseCase,
    ListAdminsUseCase,
    ListBlacklistMatchesUseCase,
    ListUsersUseCase,
    PromoteToAdminUseCase,
    SetUserDiscountUseCase,
    SetUserTrialAvailabilityUseCase,
    UnbindTelegramIdUseCase,
    UnblockBlacklistMatchesUseCase,
    UnblockUserUseCase,
    UpdateAdminUseCase,
    UpdateOwnSecuritySettingsUseCase,
)

router = APIRouter(prefix="/users", tags=["users"])
admins_router = APIRouter(prefix="/admins", tags=["admins"])


def _to_admin_response(user: UserDto) -> AdminResponse:
    return AdminResponse.model_validate(
        {
            **dict(user),
            "role_permissions": sorted(p.value for p in ROLE_PERMISSIONS.get(user.role, set())),
            "effective_permissions": effective_permission_names(user),
        }
    )


@router.get("/me/security", response_model=SecurityResponse)
@inject
async def get_own_security(
    request: Request,
    use_case: FromDishka[GetCurrentUserUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> SecurityResponse:
    current = await use_case(actor)
    return SecurityResponse.model_validate(
        {"ip_allowlist": current.ip_allowlist, "client_ip": resolve_client_ip(request)}
    )


@router.put("/me/security", response_model=SecurityResponse, responses=error_responses(400))
@inject
async def update_own_security(
    payload: UpdateSecurityRequest,
    request: Request,
    use_case: FromDishka[UpdateOwnSecuritySettingsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> SecurityResponse:
    updated = await use_case(
        actor,
        UpdateSecuritySettingsDto(
            ip_allowlist=payload.ip_allowlist,
            client_ip=resolve_client_ip(request),
        ),
    )
    return SecurityResponse.model_validate(
        {"ip_allowlist": updated.ip_allowlist, "client_ip": resolve_client_ip(request)}
    )


@router.get("", response_model=UserPageResponse)
@inject
async def list_users(
    use_case: FromDishka[ListUsersUseCase],
    actor: Actor = Depends(require_admin),
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
    role: Optional[Role] = None,
    is_blocked: Optional[bool] = None,
    include_staff: bool = False,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    has_discount: Optional[bool] = None,
    has_subscription: Optional[bool] = None,
    is_trial_available: Optional[bool] = None,
    blocked_by: Optional[BlacklistMatchOrigin] = None,
    deleted: DeletedFilter = "exclude",
    sort: UserSort = "created_at",
    descending: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> UserPageResponse:
    users, total = await use_case(
        actor,
        ListUsersDto(
            search=search,
            role=role,
            is_blocked=is_blocked,
            include_staff=include_staff,
            created_from=range_start_utc(created_from),
            created_to=range_end_utc(created_to),
            has_discount=has_discount,
            has_subscription=has_subscription,
            is_trial_available=is_trial_available,
            blocked_by=blocked_by,
            deleted=deleted,
            sort=sort,
            descending=descending,
            page=page,
            page_size=page_size,
        ),
    )
    items = [UserListItemResponse.model_validate(u, from_attributes=True) for u in users]
    return UserPageResponse(items=items, total=total)


@router.get("/{user_id:int}", response_model=UserListItemResponse, responses=error_responses(404))
@inject
async def get_user(
    user_id: int,
    use_case: FromDishka[GetUserUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    user = await use_case(actor, user_id)
    return UserListItemResponse.model_validate(user, from_attributes=True)


@router.get(
    "/{user_id:int}/registration",
    response_model=UserRegistrationResponse,
    responses=error_responses(404),
)
@inject
async def get_user_registration(
    user_id: int,
    use_case: FromDishka[GetUserRegistrationUseCase],
    actor: Actor = Depends(require_admin),
) -> UserRegistrationResponse:
    registration = await use_case(actor, user_id)
    return UserRegistrationResponse.model_validate(
        {"registration": registration}, from_attributes=True
    )


@router.get("/summary", response_model=UserListStatsResponse)
@inject
async def get_user_summary(
    use_case: FromDishka[GetUserListStatsUseCase],
    actor: Actor = Depends(require_admin),
    include_staff: bool = False,
) -> UserListStatsResponse:
    stats = await use_case(actor, GetUserListStatsDto(include_staff=include_staff))
    return UserListStatsResponse.model_validate(stats, from_attributes=True)


@router.get("/blacklist-matches", response_model=BlacklistMatchPageResponse)
@inject
async def list_blacklist_matches(
    use_case: FromDishka[ListBlacklistMatchesUseCase],
    actor: Actor = Depends(require_admin),
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
    origin: Optional[BlacklistMatchOrigin] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> BlacklistMatchPageResponse:
    result = await use_case(
        actor,
        ListBlacklistMatchesDto(
            search=search,
            origin=origin,
            page=page,
            page_size=page_size,
        ),
    )
    return BlacklistMatchPageResponse.model_validate(result, from_attributes=True)


@router.post("/bulk/unblock-blacklist-matches", response_model=UnblockBlacklistMatchesResponse)
@inject
async def unblock_blacklist_matches(
    request: Request,
    use_case: FromDishka[UnblockBlacklistMatchesUseCase],
    actor: Actor = Depends(require_admin),
) -> UnblockBlacklistMatchesResponse:
    count = await use_case(actor, UnblockBlacklistMatchesDto(client_ip=resolve_client_ip(request)))
    return UnblockBlacklistMatchesResponse(unblocked=count)


@router.patch(
    "/{user_id:int}/discount",
    response_model=UserListItemResponse,
    responses=error_responses(400, 404),
)
@inject
async def set_user_discount(
    user_id: int,
    payload: SetDiscountRequest,
    request: Request,
    use_case: FromDishka[SetUserDiscountUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor,
        SetUserDiscountDto(
            user_id=user_id,
            personal_discount=payload.personal_discount,
            purchase_discount=payload.purchase_discount,
            client_ip=resolve_client_ip(request),
        ),
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.patch(
    "/{user_id:int}/trial",
    response_model=UserListItemResponse,
    responses=error_responses(404),
)
@inject
async def set_user_trial_availability(
    user_id: int,
    payload: SetTrialAvailabilityRequest,
    request: Request,
    use_case: FromDishka[SetUserTrialAvailabilityUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor,
        SetUserTrialAvailabilityDto(
            user_id=user_id,
            is_trial_available=payload.is_trial_available,
            client_ip=resolve_client_ip(request),
        ),
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.put(
    "/{user_id:int}/telegram",
    response_model=UserListItemResponse,
    responses=error_responses(400, 404, 409),
)
@inject
async def bind_user_telegram(
    user_id: int,
    payload: BindTelegramRequest,
    request: Request,
    use_case: FromDishka[BindTelegramIdUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor,
        BindTelegramDto(
            user_id=user_id,
            telegram_id=payload.telegram_id,
            client_ip=resolve_client_ip(request),
        ),
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.delete(
    "/{user_id:int}/telegram",
    response_model=UserListItemResponse,
    responses=error_responses(404, 409),
)
@inject
async def unbind_user_telegram(
    user_id: int,
    request: Request,
    use_case: FromDishka[UnbindTelegramIdUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor, UnbindTelegramDto(user_id=user_id, client_ip=resolve_client_ip(request))
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.post(
    "/{user_id:int}/actions/block",
    response_model=UserListItemResponse,
    responses=error_responses(404),
)
@inject
async def block_user(
    user_id: int,
    request: Request,
    use_case: FromDishka[BlockUserUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor, BlockUserDto(user_id=user_id, client_ip=resolve_client_ip(request))
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.post(
    "/{user_id:int}/actions/unblock",
    response_model=UserListItemResponse,
    responses=error_responses(404),
)
@inject
async def unblock_user(
    user_id: int,
    request: Request,
    use_case: FromDishka[UnblockUserUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor, UnblockUserDto(user_id=user_id, client_ip=resolve_client_ip(request))
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.post(
    "/{user_id:int}/actions/clear-email-undeliverable",
    response_model=UserListItemResponse,
    responses=error_responses(404),
)
@inject
async def clear_email_undeliverable(
    user_id: int,
    request: Request,
    use_case: FromDishka[ClearEmailUndeliverableUseCase],
    actor: Actor = Depends(require_admin),
) -> UserListItemResponse:
    updated = await use_case(
        actor, ClearEmailUndeliverableDto(user_id=user_id, client_ip=resolve_client_ip(request))
    )
    return UserListItemResponse.model_validate(updated, from_attributes=True)


@router.delete(
    "/{user_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_user(
    user_id: int,
    request: Request,
    use_case: FromDishka[DeleteUserUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, DeleteUserDto(user_id=user_id, client_ip=resolve_client_ip(request)))


@admins_router.get("", response_model=AdminListResponse)
@inject
async def list_admins(
    use_case: FromDishka[ListAdminsUseCase],
    actor: Actor = Depends(require_admin),
) -> AdminListResponse:
    result = await use_case(actor)
    items = [_to_admin_response(a) for a in result.admins]
    return AdminListResponse(
        items=items, total=len(items), customer_sign_in_ids=sorted(result.customer_sign_in_ids)
    )


@admins_router.get(
    "/{user_id:int}", response_model=AdminDetailResponse, responses=error_responses(404)
)
@inject
async def get_admin(
    user_id: int,
    use_case: FromDishka[GetAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> AdminDetailResponse:
    detail = await use_case(actor, user_id)
    return AdminDetailResponse.model_validate(
        {
            **_to_admin_response(detail.admin).model_dump(),
            "can_sign_in_after_demote": detail.can_sign_in_after_demote,
        }
    )


@admins_router.post(
    "",
    response_model=AdminWithPasswordResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 409),
)
@inject
async def create_admin(
    payload: CreateAdminRequest,
    request: Request,
    use_case: FromDishka[CreateAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> AdminWithPasswordResponse:
    created = await use_case(
        actor,
        CreateAdminDto(
            login=payload.login,
            client_ip=resolve_client_ip(request),
            permission_grants=payload.permission_grants,
            permission_revokes=payload.permission_revokes,
        ),
    )
    return AdminWithPasswordResponse(
        admin=_to_admin_response(created.admin), password=created.password
    )


@admins_router.post(
    "/actions/promote",
    response_model=AdminPromoteResponse,
    responses=error_responses(400, 404, 409),
)
@inject
async def promote_admin(
    payload: PromoteAdminRequest,
    request: Request,
    use_case: FromDishka[PromoteToAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> AdminPromoteResponse:
    promoted = await use_case(
        actor,
        PromoteToAdminDto(
            user_id=payload.user_id,
            login=payload.login,
            client_ip=resolve_client_ip(request),
        ),
    )
    return AdminPromoteResponse(
        admin=_to_admin_response(promoted.admin), password=promoted.password
    )


@admins_router.patch(
    "/{user_id:int}", response_model=AdminResponse, responses=error_responses(400, 404, 409)
)
@inject
async def update_admin(
    user_id: int,
    payload: UpdateAdminRequest,
    request: Request,
    use_case: FromDishka[UpdateAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> AdminResponse:
    updated = await use_case(
        actor,
        UpdateAdminDto(
            user_id=user_id,
            client_ip=resolve_client_ip(request),
            permission_grants=payload.permission_grants,
            permission_revokes=payload.permission_revokes,
        ),
    )
    return _to_admin_response(updated)


@admins_router.post(
    "/{user_id:int}/actions/demote",
    response_model=UserResponse,
    responses=error_responses(404, 409),
)
@inject
async def demote_admin(
    user_id: int,
    request: Request,
    use_case: FromDishka[DemoteAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> UserResponse:
    demoted = await use_case(
        actor, DemoteAdminDto(user_id=user_id, client_ip=resolve_client_ip(request))
    )
    return UserResponse.model_validate(demoted, from_attributes=True)


@admins_router.delete(
    "/{user_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_admin(
    user_id: int,
    request: Request,
    use_case: FromDishka[DeleteAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, DeleteAdminDto(user_id=user_id, client_ip=resolve_client_ip(request)))
