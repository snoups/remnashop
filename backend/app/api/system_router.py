from datetime import datetime
from typing import Literal, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.public import get_current_actor
from app.core.config import AppConfig
from app.core.constants import REPOSITORY
from app.core.enums import Role
from app.core.security.permissions import (
    PERMISSION_METADATA,
    ROLE_PERMISSIONS,
    TOKEN_GRANTABLE_PERMISSIONS,
    Permission,
)
from app.modules.users import UserDto

router = APIRouter(tags=["system"])


class GitInfoResponse(BaseModel):
    commit_sha: Optional[str]
    commit_date: Optional[datetime]
    branch: Optional[str]
    is_official_build: bool


class SystemMetadataResponse(BaseModel):
    version: str
    repository_url: str
    git: GitInfoResponse


class PermissionCatalogEntry(BaseModel):
    permission: Permission
    resource: str
    kind: Literal["read", "write"]
    token_grantable: bool
    admin_default: bool


class PermissionCatalogResponse(BaseModel):
    entries: list[PermissionCatalogEntry]


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
    _: UserDto = Depends(get_current_actor),
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
    return PermissionCatalogResponse(
        entries=[
            PermissionCatalogEntry(
                permission=permission,
                resource=meta.resource,
                kind=meta.kind,
                token_grantable=permission in TOKEN_GRANTABLE_PERMISSIONS,
                admin_default=permission in ROLE_PERMISSIONS[Role.ADMIN],
            )
            for permission, meta in PERMISSION_METADATA.items()
        ]
    )
