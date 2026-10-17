import json
import re
from pathlib import Path
from typing import Final

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

import app as app_package
from app.api.app import get_app
from app.api.dependencies.public import get_current_actor
from app.api.errors import ApiError, register_error_handlers
from app.core.config import AppConfig
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RemnawavePanelUnavailableError,
    ValidationError,
)

_APP_DIR: Final[Path] = Path(app_package.__file__).parent
_LOCALES_DIR: Final[Path] = _APP_DIR.parents[1] / "frontend" / "src" / "shared" / "i18n" / "locales"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/not-found")
    async def not_found() -> None:
        raise NotFoundError("Plan '7' not found", code=ErrorCode.PLAN_NOT_FOUND)

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("Login already taken", code=ErrorCode.LOGIN_TAKEN)

    @app.get("/invalid")
    async def invalid() -> None:
        raise ValidationError("Image must be square", code=ErrorCode.IMAGE_NOT_SQUARE)

    @app.get("/unauthenticated")
    async def unauthenticated() -> None:
        raise AuthenticationError("Invalid login or password", code=ErrorCode.INVALID_CREDENTIALS)

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise PermissionDeniedError

    @app.get("/panel-down")
    async def panel_down() -> None:
        raise RemnawavePanelUnavailableError("circuit breaker is open")

    @app.get("/api-error")
    async def api_error() -> None:
        raise ApiError(status.HTTP_403_FORBIDDEN, "CSRF check failed", code=ErrorCode.CSRF_FAILED)

    @app.get("/plain-http")
    async def plain_http() -> None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @app.get("/typed/{item_id}")
    async def typed(item_id: int) -> None: ...

    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "status_code", "body"),
    [
        ("/not-found", 404, {"detail": "Plan '7' not found", "code": "PLAN_NOT_FOUND"}),
        ("/conflict", 409, {"detail": "Login already taken", "code": "LOGIN_TAKEN"}),
        ("/invalid", 400, {"detail": "Image must be square", "code": "IMAGE_NOT_SQUARE"}),
        (
            "/unauthenticated",
            401,
            {"detail": "Invalid login or password", "code": "INVALID_CREDENTIALS"},
        ),
        ("/forbidden", 403, {"detail": "Permission denied", "code": "PERMISSION_DENIED"}),
        ("/api-error", 403, {"detail": "CSRF check failed", "code": "CSRF_FAILED"}),
        ("/plain-http", 404, {"detail": "Not Found", "code": "NOT_FOUND"}),
    ],
)
def test_errors_carry_detail_and_code(
    client: TestClient, path: str, status_code: int, body: dict[str, str]
) -> None:
    response = client.get(path)

    assert response.status_code == status_code
    assert response.json() == body


def test_panel_outage_hides_internal_breaker_state(client: TestClient) -> None:
    response = client.get("/panel-down")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Remnawave panel is temporarily unavailable",
        "code": "REMNAWAVE_UNAVAILABLE",
    }


def test_unhandled_exception_hides_its_message() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret internals")

    response = TestClient(app, raise_server_exceptions=False).get("/crash")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "code": "INTERNAL_ERROR"}


def test_unrouted_path_and_request_validation_get_codes(client: TestClient) -> None:
    unrouted = client.get("/nowhere")
    invalid = client.get("/typed/abc")

    assert unrouted.json()["code"] == "NOT_FOUND"
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "REQUEST_INVALID"
    assert isinstance(invalid.json()["detail"], list)


def _api_routes(config: AppConfig) -> list[APIRoute]:
    return [
        route
        for route in get_app(config).routes
        if isinstance(route, APIRoute) and route.include_in_schema
    ]


def test_operation_ids_are_unique_handler_names(config: AppConfig) -> None:
    schema = get_app(config).openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
    ]

    assert len(operation_ids) == len(set(operation_ids))
    assert "list_users" in operation_ids


def test_authenticated_routes_document_401_and_403(config: AppConfig) -> None:
    def depends_on_auth(dependant) -> bool:  # type: ignore[no-untyped-def]
        return any(
            sub.call is get_current_actor or depends_on_auth(sub) for sub in dependant.dependencies
        )

    routes = [route for route in _api_routes(config) if depends_on_auth(route.dependant)]

    assert routes
    undocumented = [route.path for route in routes if not {401, 403} <= set(route.responses)]
    assert undocumented == []


def test_every_operation_documents_422_and_429(config: AppConfig) -> None:
    schema = get_app(config).openapi()
    missing = [
        f"{method.upper()} {path}"
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if not {"422", "429"} <= set(operation["responses"])
    ]

    assert missing == []


def test_no_route_overrides_the_global_422_schema(config: AppConfig) -> None:
    schema = get_app(config).openapi()
    overridden = [
        f"{method.upper()} {path}"
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if "RequestInvalidResponse" not in str(operation["responses"]["422"])
    ]

    assert overridden == []


def test_every_error_code_is_used() -> None:
    sources = "".join(
        path.read_text() for path in _APP_DIR.rglob("*.py") if path.name != "error_codes.py"
    )
    unused = [code.name for code in ErrorCode if f"ErrorCode.{code.name}" not in sources]

    assert unused == []


@pytest.mark.skipif(not _LOCALES_DIR.exists(), reason="frontend sources not present")
@pytest.mark.parametrize("locale", ["en", "ru"])
def test_every_error_code_is_translated(locale: str) -> None:
    translations = json.loads((_LOCALES_DIR / f"{locale}.json").read_text())["apiErrors"]

    assert sorted(set(ErrorCode) - set(translations)) == []
    assert sorted(set(translations) - set(ErrorCode)) == []
    assert all(re.search(r"\S", text) for text in translations.values())


def test_a_database_error_other_than_an_overflow_stays_a_500() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/crash")
    async def crash() -> None:
        raise DBAPIError("SELECT 1", None, RuntimeError("deadlock detected"))

    response = TestClient(app, raise_server_exceptions=False).get("/crash")

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
