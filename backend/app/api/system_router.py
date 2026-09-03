from datetime import datetime
from typing import Literal, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.__version__ import __version__
from app.api.dependencies.public import get_current_actor
from app.core.config import AppConfig
from app.core.constants import REPOSITORY
from app.core.security.permissions import PERMISSION_METADATA, Permission
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


class PermissionCatalogResponse(BaseModel):
    entries: list[PermissionCatalogEntry]


@router.get("/system/metadata", response_model=SystemMetadataResponse)
@inject
async def system_metadata(
    config: FromDishka[AppConfig],
    _: UserDto = Depends(get_current_actor),
) -> SystemMetadataResponse:
    # BUILD_TAG (CI --build-arg) wins when present; __version__.py is the
    # dev-without-CI fallback. is_official_build gates the update check --
    # only a CI-baked artifact is safe to compare against GitHub releases.
    git = GitInfoResponse(
        commit_sha=config.build.commit,
        commit_date=datetime.fromisoformat(config.build.time) if config.build.time else None,
        branch=config.build.branch,
        is_official_build=config.build.is_set,
    )
    return SystemMetadataResponse(
        version=config.build.tag or __version__, repository_url=REPOSITORY, git=git
    )


@router.get("/permissions/catalog", response_model=PermissionCatalogResponse)
async def permissions_catalog(
    _: UserDto = Depends(get_current_actor),
) -> PermissionCatalogResponse:
    return PermissionCatalogResponse(
        entries=[
            PermissionCatalogEntry(permission=permission, resource=meta.resource, kind=meta.kind)
            for permission, meta in PERMISSION_METADATA.items()
        ]
    )
