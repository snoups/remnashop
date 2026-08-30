from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from app.__version__ import __version__
from app.api.dependencies.public import get_current_actor
from app.api.lifespan import lifespan
from app.core.config import AppConfig
from app.core.constants import API_V1, REPOSITORY
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import PERMISSION_METADATA, Permission
from app.modules.api_tokens.api import admin_router as api_tokens_admin_router
from app.modules.auth.api import admin_router as auth_admin_router
from app.modules.auth.api import router as auth_router
from app.modules.auth.api import sessions_router as auth_sessions_router
from app.modules.banners.api import admin_router as banners_admin_router
from app.modules.event_log.api import event_log_admin_router
from app.modules.gateways.api import admin_router as gateways_admin_router
from app.modules.plans.api import admin_router as plans_admin_router
from app.modules.plans.api import public_router as plans_public_router
from app.modules.promocodes.api import admin_router as promocodes_admin_router
from app.modules.promocodes.api import public_router as promocodes_public_router
from app.modules.settings.api import admin_router as settings_admin_router
from app.modules.settings.api import router as settings_router
from app.modules.subscriptions.api import addons_router as subscriptions_addons_router
from app.modules.subscriptions.api import admin_router as subscriptions_admin_router
from app.modules.subscriptions.api import router as subscriptions_webhook_router
from app.modules.translations.api import admin_router as translations_admin_router
from app.modules.users import UserDto
from app.modules.users.api import admin_router as users_admin_router
from app.modules.users.api import admins_router as users_admins_router


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


FRONTEND_DIST: Path = Path("/opt/remnashop/frontend/dist")


def resolve_cors(origins: list[str]) -> tuple[list[str], bool]:
    if "*" in origins:
        logger.warning("CORS origins set to '*'; disabling allow_credentials for safety")
        return origins, False
    return origins, True


def _setup_spa_serving(app: FastAPI, frontend_dist: Path) -> None:
    if not frontend_dist.exists():
        return

    root = frontend_dist.resolve()

    app.mount("/assets", StaticFiles(directory=root / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html")


def get_app(config: AppConfig, frontend_dist: Path = FRONTEND_DIST) -> FastAPI:
    app: FastAPI = FastAPI(
        lifespan=lifespan,
        title="Remnashop API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    cors_origins, allow_credentials = resolve_cors(list(config.origins))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix=API_V1)
    app.include_router(auth_admin_router, prefix=API_V1)
    app.include_router(auth_sessions_router, prefix=API_V1)
    app.include_router(users_admin_router, prefix=API_V1)
    app.include_router(users_admins_router, prefix=API_V1)
    app.include_router(settings_admin_router, prefix=API_V1)
    app.include_router(settings_router, prefix=API_V1)
    app.include_router(plans_admin_router, prefix=API_V1)
    app.include_router(plans_public_router, prefix=API_V1)
    app.include_router(promocodes_admin_router, prefix=API_V1)
    app.include_router(promocodes_public_router, prefix=API_V1)
    app.include_router(subscriptions_admin_router, prefix=API_V1)
    app.include_router(subscriptions_addons_router, prefix=API_V1)
    app.include_router(subscriptions_webhook_router, prefix=API_V1)
    app.include_router(banners_admin_router, prefix=API_V1)
    app.include_router(event_log_admin_router, prefix=API_V1)
    app.include_router(gateways_admin_router, prefix=API_V1)
    app.include_router(api_tokens_admin_router, prefix=API_V1)
    app.include_router(translations_admin_router, prefix=API_V1)

    # Each further module contributes its own routers here once it has an api/ package.

    @app.get(f"{API_V1}/system/metadata", response_model=SystemMetadataResponse)
    async def system_metadata(_: UserDto = Depends(get_current_actor)) -> SystemMetadataResponse:
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

    @app.get(f"{API_V1}/permissions/catalog", response_model=PermissionCatalogResponse)
    async def permissions_catalog(
        _: UserDto = Depends(get_current_actor),
    ) -> PermissionCatalogResponse:
        return PermissionCatalogResponse(
            entries=[
                PermissionCatalogEntry(
                    permission=permission, resource=meta.resource, kind=meta.kind
                )
                for permission, meta in PERMISSION_METADATA.items()
            ]
        )

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(_: Request, __: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Permission denied"}
        )

    if config.swagger_enabled:

        @app.get("/docs", include_in_schema=False)
        async def swagger_ui() -> HTMLResponse:
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title=f"{app.title} - Swagger UI",
                swagger_ui_parameters={"persistAuthorization": True},
            )

        @app.get("/redoc", include_in_schema=False)
        async def redoc_ui() -> HTMLResponse:
            return get_redoc_html(
                openapi_url="/openapi.json",
                title=f"{app.title} - ReDoc",
            )

        @app.get("/openapi.json", include_in_schema=False)
        async def openapi_schema() -> dict:
            api_routes = [r for r in app.routes if getattr(r, "include_in_schema", True)]
            return get_openapi(title=app.title, version=app.version, routes=api_routes)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    _setup_spa_serving(app, frontend_dist)

    logger.info("API FastAPI application initialized")
    return app
