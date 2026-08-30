from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Role
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security.permissions import PermissionPolicy
from app.core.utils.http import resolve_client_ip
from app.modules.users.api.schemas import (
    AdminPromoteResponse,
    AdminResponse,
    AdminWithPasswordResponse,
    CreateAdminRequest,
    CurrentUserResponse,
    PromoteAdminRequest,
    SecurityResponse,
    UpdateAdminRequest,
    UpdateOwnProfileRequest,
    UpdateSecurityRequest,
    UserPageResponse,
    UserResponse,
)
from app.modules.users.dto import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, UserDto
from app.modules.users.usecases import (
    CreateAdminDto,
    CreateAdminUseCase,
    DeleteAdminDto,
    DeleteAdminUseCase,
    DeleteUserDto,
    DeleteUserUseCase,
    DemoteAdminDto,
    DemoteAdminUseCase,
    GetCurrentUserUseCase,
    ListAdminsUseCase,
    ListUsersInput,
    ListUsersUseCase,
    PromoteToAdminDto,
    PromoteToAdminUseCase,
    UpdateAdminDto,
    UpdateAdminUseCase,
    UpdateOwnProfileDto,
    UpdateOwnProfileUseCase,
    UpdateOwnSecuritySettingsUseCase,
    UpdateSecuritySettingsDto,
)

router = APIRouter(prefix="/users", tags=["users"])
admins_router = APIRouter(prefix="/admins", tags=["admins"])


def _conflict_or_validation_status(error: ConflictError | ValidationError) -> int:
    if isinstance(error, ConflictError):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def _parse_role(value: Optional[str]) -> Optional[Role]:
    if value is None:
        return None
    try:
        return Role[value]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid role: {value}"
        ) from None


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
        created_at=user.created_at,
        permission_grants=list(user.permission_grants or []),
        permission_revokes=list(user.permission_revokes or []),
        effective_permissions=sorted(p.value for p in PermissionPolicy.effective_permissions(user)),
    )


def _to_user_response(user: UserDto) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        role=str(user.role),
        telegram_id=user.telegram_id,
        username=user.username,
        email=user.email,
        login=user.login,
        language=str(user.language),
        is_blocked=user.is_blocked,
        created_at=user.created_at,
    )


@router.get("/me", response_model=CurrentUserResponse)
@inject
async def get_me(
    use_case: FromDishka[GetCurrentUserUseCase],
    actor: UserDto = Depends(require_admin),
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
    )


@router.patch("/me", response_model=CurrentUserResponse)
@inject
async def update_me(
    payload: UpdateOwnProfileRequest,
    use_case: FromDishka[UpdateOwnProfileUseCase],
    actor: UserDto = Depends(require_admin),
) -> CurrentUserResponse:
    try:
        updated = await use_case(
            actor,
            UpdateOwnProfileDto(
                name=payload.name,
                current_password=payload.current_password,
                new_password=payload.new_password,
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return CurrentUserResponse(
        id=updated.id,
        login=updated.login,
        name=updated.name,
        role=str(updated.role),
        effective_permissions=sorted(
            p.value for p in PermissionPolicy.effective_permissions(updated)
        ),
    )


@router.get("/me/security", response_model=SecurityResponse)
async def get_own_security(actor: UserDto = Depends(require_admin)) -> SecurityResponse:
    return SecurityResponse(ip_allowlist=actor.ip_allowlist or [])


@router.put("/me/security", response_model=SecurityResponse)
@inject
async def update_own_security(
    payload: UpdateSecurityRequest,
    request: Request,
    use_case: FromDishka[UpdateOwnSecuritySettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> SecurityResponse:
    try:
        updated = await use_case(
            actor,
            UpdateSecuritySettingsDto(
                ip_allowlist=payload.ip_allowlist,
                client_ip=resolve_client_ip(request),
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return SecurityResponse(ip_allowlist=updated.ip_allowlist or [])


@router.get("", response_model=UserPageResponse)
@inject
async def list_users(
    use_case: FromDishka[ListUsersUseCase],
    actor: UserDto = Depends(require_admin),
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_blocked: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> UserPageResponse:
    users, total = await use_case(
        actor,
        ListUsersInput(
            search=search,
            role=_parse_role(role),
            is_blocked=is_blocked,
            page=page,
            page_size=page_size,
        ),
    )
    return UserPageResponse(items=[_to_user_response(u) for u in users], total=total)


@admins_router.get("", response_model=list[AdminResponse])
@inject
async def list_admins(
    use_case: FromDishka[ListAdminsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[AdminResponse]:
    admins = await use_case(actor)
    return [_to_admin_response(a) for a in admins]


@admins_router.post(
    "", response_model=AdminWithPasswordResponse, status_code=status.HTTP_201_CREATED
)
@inject
async def create_admin(
    payload: CreateAdminRequest,
    request: Request,
    use_case: FromDishka[CreateAdminUseCase],
    actor: UserDto = Depends(require_admin),
) -> AdminWithPasswordResponse:
    try:
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
    except (ConflictError, ValidationError) as error:
        code = _conflict_or_validation_status(error)
        raise HTTPException(status_code=code, detail=str(error)) from error
    return AdminWithPasswordResponse(admin=_to_admin_response(admin), password=password)


@admins_router.post("/promote", response_model=AdminPromoteResponse)
@inject
async def promote_admin(
    payload: PromoteAdminRequest,
    request: Request,
    use_case: FromDishka[PromoteToAdminUseCase],
    actor: UserDto = Depends(require_admin),
) -> AdminPromoteResponse:
    try:
        admin, password = await use_case(
            actor,
            PromoteToAdminDto(
                email=payload.email,
                telegram_username=payload.telegram_username,
                login=payload.login,
                client_ip=resolve_client_ip(request),
                permission_grants=payload.permission_grants,
                permission_revokes=payload.permission_revokes,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ConflictError, ValidationError) as error:
        code = _conflict_or_validation_status(error)
        raise HTTPException(status_code=code, detail=str(error)) from error
    return AdminPromoteResponse(admin=_to_admin_response(admin), password=password)


@admins_router.patch("/{user_id}", response_model=AdminResponse)
@inject
async def update_admin(
    user_id: int,
    payload: UpdateAdminRequest,
    request: Request,
    use_case: FromDishka[UpdateAdminUseCase],
    actor: UserDto = Depends(require_admin),
) -> AdminResponse:
    try:
        updated = await use_case(
            actor,
            UpdateAdminDto(
                user_id=user_id,
                client_ip=resolve_client_ip(request),
                permission_grants=payload.permission_grants,
                permission_revokes=payload.permission_revokes,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ConflictError, ValidationError) as error:
        code = _conflict_or_validation_status(error)
        raise HTTPException(status_code=code, detail=str(error)) from error
    return _to_admin_response(updated)


@admins_router.post("/{user_id}/demote", response_model=AdminResponse)
@inject
async def demote_admin(
    user_id: int,
    request: Request,
    use_case: FromDishka[DemoteAdminUseCase],
    actor: UserDto = Depends(require_admin),
) -> AdminResponse:
    try:
        demoted = await use_case(
            actor, DemoteAdminDto(user_id=user_id, client_ip=resolve_client_ip(request))
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_admin_response(demoted)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_user(
    user_id: int,
    request: Request,
    use_case: FromDishka[DeleteUserUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, DeleteUserDto(user_id=user_id, client_ip=resolve_client_ip(request)))
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@admins_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_admin(
    user_id: int,
    request: Request,
    use_case: FromDishka[DeleteAdminUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, DeleteAdminDto(user_id=user_id, client_ip=resolve_client_ip(request)))
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
