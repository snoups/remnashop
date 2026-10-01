from pathlib import Path
from typing import Final

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.types import Scope

from app.__version__ import __version__
from app.api.dependencies.public import get_current_actor
from app.api.dependencies.rate_limit import global_rate_limit
from app.api.errors import (
    GLOBAL_ERROR_RESPONSES,
    document_auth_errors,
    register_error_handlers,
)
from app.api.lifespan import lifespan
from app.api.middlewares import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.api.probes_router import router as probes_router
from app.api.routers import ROUTERS
from app.api.system_router import router as system_router
from app.core.config import AppConfig
from app.core.constants import API_V1

FRONTEND_DIST: Final[Path] = Path("/opt/remnashop/frontend/dist")
# Vite hashes every file name under assets/, so a URL never changes content
_ASSETS_CACHE_CONTROL: Final[str] = "public, max-age=31536000, immutable"


def resolve_cors(origins: list[str]) -> tuple[list[str], bool]:
    if "*" in origins:
        logger.warning("CORS origins set to '*'; disabling allow_credentials for safety")
        return origins, False
    return origins, True


class _ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            response.headers["Cache-Control"] = _ASSETS_CACHE_CONTROL
        return response


def _setup_spa_serving(app: FastAPI, frontend_dist: Path) -> None:
    if not frontend_dist.exists():
        return

    root = frontend_dist.resolve()

    # gzip scoped to static bundles: API responses, backups and images stay uncompressed
    app.mount(
        "/assets",
        GZipMiddleware(_ImmutableStaticFiles(directory=root / "assets")),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})


# handler names are unique across routers; keeps operationIds readable for generated clients
def _operation_id(route: APIRoute) -> str:
    return route.name


def get_app(config: AppConfig, frontend_dist: Path = FRONTEND_DIST) -> FastAPI:
    app: FastAPI = FastAPI(
        lifespan=lifespan,
        title="Remnashop API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(global_rate_limit)],
        generate_unique_id_function=_operation_id,
        responses=GLOBAL_ERROR_RESPONSES,
    )
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    cors_origins, allow_credentials = resolve_cors(list(config.origins))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in ROUTERS:
        app.include_router(router, prefix=API_V1)
    app.include_router(system_router, prefix=API_V1)

    register_error_handlers(app)
    document_auth_errors(app, get_current_actor)

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

    app.include_router(probes_router)

    Instrumentator().instrument(app, metric_namespace="remnashop").expose(
        app, include_in_schema=False
    )

    _setup_spa_serving(app, frontend_dist)

    logger.info("API FastAPI application initialized")
    return app
