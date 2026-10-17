import hashlib
from pathlib import Path
from typing import Final, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, FastAPI, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.types import Scope

from app.api.dependencies.public import get_current_actor
from app.api.dependencies.rate_limit import global_rate_limit
from app.api.errors import (
    GLOBAL_ERROR_RESPONSES,
    ApiError,
    document_auth_errors,
    register_error_handlers,
)
from app.api.lifespan import lifespan
from app.api.middlewares import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.api.probes_router import router as probes_router
from app.api.routers import ROUTERS
from app.api.system_router import router as system_router
from app.core.config import AppConfig
from app.core.constants import (
    API_V1,
    DOCS_COOKIE_NAME,
    DOCS_PATH,
    REDIS_KEY_PREFIX,
    TIME_1M,
    TTL_2H,
)
from app.core.error_codes import ErrorCode
from app.core.security import create_docs_token, is_valid_docs_token
from app.core.utils.http import resolve_client_ip

_DOCS_OTT_USED_KEY: Final[str] = f"{REDIS_KEY_PREFIX}docs:ott-used:"
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

    # registered after every real route: an unknown API path must not get the SPA's index.html
    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def unknown_api_route(rest: str) -> None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "Not Found", code=ErrorCode.NOT_FOUND)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})


def _setup_docs(app: FastAPI, config: AppConfig) -> None:
    secret = config.jwt_secret.get_secret_value()
    openapi_url = f"{DOCS_PATH}/openapi.json"

    async def _enter(
        request: Request, redis: Redis, ott: Optional[str], page: HTMLResponse
    ) -> Response:
        if ott is not None:
            # one exchange per ticket: a ticket seen in a log or history is spent
            used_key = f"{_DOCS_OTT_USED_KEY}{hashlib.sha256(ott.encode()).hexdigest()}"
            if not is_valid_docs_token(ott, "ott", secret) or not await redis.set(
                used_key, 1, nx=True, ex=TIME_1M
            ):
                raise ApiError(
                    status.HTTP_401_UNAUTHORIZED,
                    "Docs ticket is invalid or expired",
                    code=ErrorCode.TOKEN_INVALID,
                )
            logger.warning(f"Docs access granted to IP '{resolve_client_ip(request)}'")
            response = RedirectResponse(request.url.path, status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                DOCS_COOKIE_NAME,
                create_docs_token("access", TTL_2H, secret),
                max_age=TTL_2H,
                path=DOCS_PATH,
                httponly=True,
                secure=config.secure_cookies,
                samesite="lax",
            )
            return response
        _require_docs_cookie(request)
        return page

    def _require_docs_cookie(request: Request) -> None:
        token = request.cookies.get(DOCS_COOKIE_NAME)
        if token is None or not is_valid_docs_token(token, "access", secret):
            raise ApiError(
                status.HTTP_401_UNAUTHORIZED,
                "Open the API docs from the dashboard",
                code=ErrorCode.NOT_AUTHENTICATED,
            )

    @app.get(DOCS_PATH, include_in_schema=False)
    @inject
    async def swagger_ui(
        request: Request, redis: FromDishka[Redis], ott: Optional[str] = None
    ) -> Response:
        page = get_swagger_ui_html(openapi_url=openapi_url, title=f"{app.title} - Swagger UI")
        return await _enter(request, redis, ott, page)

    @app.get(f"{DOCS_PATH}/redoc", include_in_schema=False)
    @inject
    async def redoc_ui(
        request: Request, redis: FromDishka[Redis], ott: Optional[str] = None
    ) -> Response:
        page = get_redoc_html(openapi_url=openapi_url, title=f"{app.title} - ReDoc")
        return await _enter(request, redis, ott, page)

    @app.get(openapi_url, include_in_schema=False)
    async def openapi_schema(request: Request) -> dict:
        _require_docs_cookie(request)
        return app.openapi()


# handler names are unique across routers; keeps operationIds readable for generated clients
def _operation_id(route: APIRoute) -> str:
    return route.name


def get_app(config: AppConfig, frontend_dist: Path = FRONTEND_DIST) -> FastAPI:
    app: FastAPI = FastAPI(
        lifespan=lifespan,
        title="Remnashop API",
        version=config.build.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(global_rate_limit)],
        generate_unique_id_function=_operation_id,
        responses=GLOBAL_ERROR_RESPONSES,
    )
    app.state.cabinet_proxy_secret = (
        config.cabinet_proxy_secret.get_secret_value() if config.cabinet_proxy_secret else None
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

    _setup_docs(app, config)

    app.include_router(probes_router)

    if config.metrics_enabled:
        Instrumentator().instrument(app, metric_namespace="remnashop").expose(
            app, include_in_schema=False
        )

    _setup_spa_serving(app, frontend_dist)

    logger.info("API FastAPI application initialized")
    return app
