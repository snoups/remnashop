from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.public import get_current_actor
from app.api.system_schemas import (
    GitInfoResponse,
    PermissionCatalogEntryResponse,
    PermissionCatalogResponse,
    SystemMetadataResponse,
)
from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import REPOSITORY
from app.core.enums import Role
from app.core.security.permissions import (
    PERMISSION_METADATA,
    ROLE_PERMISSIONS,
    TOKEN_GRANTABLE_PERMISSIONS,
)
from app.modules.users import UserDto

router = APIRouter(tags=["system"])


def parse_commit_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("/system/metadata", response_model=SystemMetadataResponse)
@inject
async def get_system_metadata(
    config: FromDishka[AppConfig],
    _: Actor = Depends(get_current_actor),
) -> SystemMetadataResponse:
    # is_official_build gates the update check --
    # only a CI-baked artifact is safe to compare against GitHub releases.
    git = GitInfoResponse(
        commit_sha=config.build.commit,
        commit_date=parse_commit_date(config.build.time),
        branch=config.build.branch,
        is_official_build=config.build.is_set,
    )
    return SystemMetadataResponse(version=config.build.version, repository_url=REPOSITORY, git=git)


@router.get("/permissions/catalog", response_model=PermissionCatalogResponse)
async def get_permissions_catalog(
    _: UserDto = Depends(require_admin_user),
) -> PermissionCatalogResponse:
    items = [
        PermissionCatalogEntryResponse(
            permission=permission,
            resource=meta.resource,
            kind=meta.kind,
            token_grantable=permission in TOKEN_GRANTABLE_PERMISSIONS,
            admin_default=permission in ROLE_PERMISSIONS[Role.ADMIN],
        )
        for permission, meta in PERMISSION_METADATA.items()
    ]
    return PermissionCatalogResponse(items=items, total=len(items))
