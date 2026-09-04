from pathlib import Path
from typing import Final

from fastapi import Depends, FastAPI, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.cors import CORSMiddleware

from app.__version__ import __version__
from app.api.dependencies.rate_limit import global_rate_limit
from app.api.lifespan import lifespan
from app.api.probes_router import router as probes_router
from app.api.routers import ROUTERS
from app.api.system_router import router as system_router
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.exceptions import PermissionDeniedError

FRONTEND_DIST: Final[Path] = Path("/opt/remnashop/frontend/dist")


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
        dependencies=[Depends(global_rate_limit)],
    )
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

    app.include_router(probes_router)

    Instrumentator().instrument(app, metric_namespace="remnashop").expose(
        app, include_in_schema=False
    )

    _setup_spa_serving(app, frontend_dist)

    logger.info("API FastAPI application initialized")
    return app
