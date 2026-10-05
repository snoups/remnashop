from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import ROLE_PERMISSIONS, PermissionPolicy
from app.core.utils.http import resolve_client_ip
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.users.api.schemas import (
    AdminListResponse,
    AdminPromoteResponse,
    AdminResponse,
    AdminWithPasswordResponse,
    BlacklistMatchPageResponse,
    CreateAdminRequest,
    CurrentUserResponse,
    PromoteAdminRequest,
    SecurityResponse,
    SetDiscountRequest,
    UnblockAllResponse,
    UpdateAdminRequest,
    UpdateOwnProfileRequest,
    UpdateSecurityRequest,
    UserListItemResponse,
    UserListStatsResponse,
    UserPageResponse,
    UserResponse,
)
from app.modules.users.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    BlacklistMatchOrigin,
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
    UpdateAdminDto,
    UpdateOwnProfileDto,
    UpdateSecuritySettingsDto,
    UserDto,
    UserSort,
)
from app.modules.users.usecases import (
    BlockUserUseCase,
    CreateAdminUseCase,
    DeleteAdminUseCase,
    DeleteUserUseCase,
    DemoteAdminUseCase,
    GetCurrentUserUseCase,
    GetUserListStatsUseCase,
    GetUserUseCase,
    ListAdminsUseCase,
    ListBlacklistMatchesUseCase,
    ListUsersUseCase,
    PromoteToAdminUseCase,
    SetUserDiscountUseCase,
    UnblockAllUsersUseCase,
    UnblockBlacklistMatchesUseCase,
    UnblockUserUseCase,
    UpdateAdminUseCase,
    UpdateOwnProfileUseCase,
    UpdateOwnSecuritySettingsUseCase,
)

router = APIRouter(prefix="/users", tags=["users"])
admins_router = APIRouter(prefix="/admins", tags=["admins"])


def _parse_role(value: Optional[str]) -> Optional[Role]:
    if value is None:
        return None
    try:
        return Role[value]
    except KeyError:
        raise ValidationError(f"Invalid role: {value}", code=ErrorCode.ROLE_INVALID) from None


def _to_admin_response(user: UserDto) -> AdminResponse:
    return AdminResponse(
        id=user.id,
        login=user.login,
        name=user.name,
        role=str(user.role),
        telegram_id=user.telegram_id,
        username=user.username,
        email=user.email,
        language=str(user.language),
        is_blocked=user.is_blocked,
        personal_discount=user.personal_discount,
        purchase_discount=user.purchase_discount,
        loyalty_discount=user.loyalty_discount,
        points=user.points,
        bonus_days=user.bonus_days,
        is_trial_available=user.is_trial_available,
        created_at=user.created_at,
        permission_grants=list(user.permission_grants or []),
        permission_revokes=list(user.permission_revokes or []),
        role_permissions=sorted(p.value for p in ROLE_PERMISSIONS.get(user.role, set())),
        effective_permissions=sorted(p.value for p in PermissionPolicy.effective_permissions(user)),
    )


@router.get("/me", response_model=CurrentUserResponse)
@inject
async def get_me(
    use_case: FromDishka[GetCurrentUserUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> CurrentUserResponse:
    current_user = await use_case(actor)
    return CurrentUserResponse(
        id=current_user.id,
        login=current_user.login,
        name=current_user.name,
        role=str(current_user.role),
        effective_permissions=sorted(
            p.value for p in PermissionPolicy.effective_permissions(current_user)
        ),
        password_change_required=current_user.password_change_required,
    )


@router.patch("/me", response_model=CurrentUserResponse, responses=error_responses(400))
@inject
async def update_me(
    payload: UpdateOwnProfileRequest,
    use_case: FromDishka[UpdateOwnProfileUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> CurrentUserResponse:
    updated = await use_case(
        actor,
        UpdateOwnProfileDto(
            name=payload.name,
            current_password=payload.current_password,
            new_password=payload.new_password,
        ),
    )
    return CurrentUserResponse(
        id=updated.id,
        login=updated.login,
        name=updated.name,
        role=str(updated.role),
        effective_permissions=sorted(
            p.value for p in PermissionPolicy.effective_permissions(updated)
        ),
        password_change_required=updated.password_change_required,
    )


@router.get("/me/security", response_model=SecurityResponse)
async def get_own_security(
    request: Request, actor: UserDto = Depends(require_admin_user)
) -> SecurityResponse:
    return SecurityResponse(
        ip_allowlist=actor.ip_allowlist or [], client_ip=resolve_client_ip(request)
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
    return SecurityResponse(
        ip_allowlist=updated.ip_allowlist or [], client_ip=resolve_client_ip(request)
    )


@router.get("", response_model=UserPageResponse)
@inject
async def list_users(
    use_case: FromDishka[ListUsersUseCase],
    actor: Actor = Depends(require_admin),
    search: Optional[str] = None,
    role: Optional[str] = None,
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
            role=_parse_role(role),
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


@router.get("/stats", response_model=UserListStatsResponse)
@inject
async def get_user_list_stats(
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
    search: Optional[str] = None,
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


@router.post("/bulk/blacklist-matches/unblock", response_model=UnblockAllResponse)
@inject
async def unblock_blacklist_matches(
    use_case: FromDishka[UnblockBlacklistMatchesUseCase],
    actor: Actor = Depends(require_admin),
) -> UnblockAllResponse:
    count = await use_case(actor)
    return UnblockAllResponse(unblocked=count)


@router.patch(
    "/{user_id}/discount", response_model=UserResponse, responses=error_responses(400, 404)
)
@inject
async def set_user_discount(
    user_id: int,
    payload: SetDiscountRequest,
    use_case: FromDishka[SetUserDiscountUseCase],
    actor: Actor = Depends(require_admin),
) -> UserResponse:
    updated = await use_case(
        actor,
        SetUserDiscountDto(
            user_id=user_id,
            personal_discount=payload.personal_discount,
            purchase_discount=payload.purchase_discount,
        ),
    )
    return UserResponse.model_validate(updated, from_attributes=True)


@router.post(
    "/{user_id}/actions/block", response_model=UserResponse, responses=error_responses(404)
)
@inject
async def block_user(
    user_id: int,
    use_case: FromDishka[BlockUserUseCase],
    actor: Actor = Depends(require_admin),
) -> UserResponse:
    updated = await use_case(actor, user_id)
    return UserResponse.model_validate(updated, from_attributes=True)


@router.post(
    "/{user_id}/actions/unblock", response_model=UserResponse, responses=error_responses(404)
)
@inject
async def unblock_user(
    user_id: int,
    use_case: FromDishka[UnblockUserUseCase],
    actor: Actor = Depends(require_admin),
) -> UserResponse:
    updated = await use_case(actor, user_id)
    return UserResponse.model_validate(updated, from_attributes=True)


@router.post("/bulk/all/unblock", response_model=UnblockAllResponse)
@inject
async def unblock_all_users(
    use_case: FromDishka[UnblockAllUsersUseCase],
    actor: Actor = Depends(require_admin),
) -> UnblockAllResponse:
    count = await use_case(actor)
    return UnblockAllResponse(unblocked=count)


@router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
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
    admins = await use_case(actor)
    items = [_to_admin_response(a) for a in admins]
    return AdminListResponse(items=items, total=len(items))


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
    admin, password = await use_case(
        actor,
        CreateAdminDto(
            login=payload.login,
            name=payload.name,
            client_ip=resolve_client_ip(request),
            permission_grants=payload.permission_grants,
            permission_revokes=payload.permission_revokes,
        ),
    )
    return AdminWithPasswordResponse(admin=_to_admin_response(admin), password=password)


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
    admin, password = await use_case(
        actor,
        PromoteToAdminDto(
            user_id=payload.user_id,
            email=payload.email,
            telegram_username=payload.telegram_username,
            login=payload.login,
            client_ip=resolve_client_ip(request),
            permission_grants=payload.permission_grants,
            permission_revokes=payload.permission_revokes,
        ),
    )
    return AdminPromoteResponse(admin=_to_admin_response(admin), password=password)


@admins_router.patch(
    "/{user_id}", response_model=AdminResponse, responses=error_responses(400, 404, 409)
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
    "/{user_id}/actions/demote", response_model=AdminResponse, responses=error_responses(404, 409)
)
@inject
async def demote_admin(
    user_id: int,
    request: Request,
    use_case: FromDishka[DemoteAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> AdminResponse:
    demoted = await use_case(
        actor, DemoteAdminDto(user_id=user_id, client_ip=resolve_client_ip(request))
    )
    return _to_admin_response(demoted)


@admins_router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404, 409)
)
@inject
async def delete_admin(
    user_id: int,
    request: Request,
    use_case: FromDishka[DeleteAdminUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, DeleteAdminDto(user_id=user_id, client_ip=resolve_client_ip(request)))
