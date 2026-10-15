from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.core.security.permissions import Permission


class GitInfoResponse(BaseModel):
    commit_sha: Optional[str]
    commit_date: Optional[datetime]
    branch: Optional[str]
    is_official_build: bool


class SystemMetadataResponse(BaseModel):
    version: str
    repository_url: str
    git: GitInfoResponse


class PermissionCatalogEntryResponse(BaseModel):
    permission: Permission
    resource: str
    kind: Literal["read", "write"]
    token_grantable: bool
    admin_default: bool


class PermissionCatalogResponse(BaseModel):
    items: list[PermissionCatalogEntryResponse]
    total: int
