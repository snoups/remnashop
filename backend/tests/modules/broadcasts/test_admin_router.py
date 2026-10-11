import datetime
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import BroadcastStatus, Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.broadcasts import BroadcastRepository
from app.modules.providers import get_module_providers
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncContainer:
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    # same fixture as tests/modules/users/test_admin_router.py
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _issue_token(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> str:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token("test-refresh-token"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, role: Role, login: str
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    return user


@pytest.fixture
def config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
async def admin_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "bcowner")
    return {"Authorization": f"Bearer {await _issue_token(owner.id, session_repository, config)}"}


def _body(text: str = "Hi { $name }") -> dict[str, Any]:
    return {
        "category": "SERVICE",
        "audience": {},
        "default_locale": "en",
        "contents": {"en": {"text": text, "button_labels": []}},
        "buttons": [],
        "promocode_id": None,
        "post_to_channel": False,
    }


async def test_create_get_update_flow(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    assert created.status_code == 201
    broadcast_id = created.json()["id"]
    assert "media_file_id" not in created.json()
    fetched = await client.get(f"/api/v1/broadcasts/{broadcast_id}", headers=admin_headers)
    assert fetched.json()["status"] == "DRAFT"
    updated = await client.put(
        f"/api/v1/broadcasts/{broadcast_id}", json=_body("Bye"), headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["contents"]["en"]["text"] == "Bye"
    assert created.json()["created_by_name"] == "bcowner"
    assert updated.json()["created_by_name"] == "bcowner"
    assert created.json()["recall_requested"] is False


async def test_invalid_html_is_400_with_code(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.post("/api/v1/broadcasts", json=_body("<div>"), headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "BROADCAST_HTML_INVALID"


async def test_list_is_paginated(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    for _ in range(3):
        await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    response = await client.get("/api/v1/broadcasts?page_size=2", headers=admin_headers)
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 3


async def test_preview_audience(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/broadcasts/actions/preview-audience",
        json={"audience": {}, "category": "SERVICE"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 0
    assert "by_locale" in response.json()


async def test_unknown_audience_field_is_422(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    body = _body()
    body["audience"] = {"foo": 1}
    response = await client.post("/api/v1/broadcasts", json=body, headers=admin_headers)
    assert response.status_code == 422


async def test_missing_broadcast_is_404(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/broadcasts/999999", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "BROADCAST_NOT_FOUND"


async def test_naive_scheduled_at_is_422(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    response = await client.post(
        f"/api/v1/broadcasts/{created.json()['id']}/actions/send",
        json={"scheduled_at": "2030-01-01T10:00:00"},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_cancel_draft_is_409(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    response = await client.post(
        f"/api/v1/broadcasts/{created.json()['id']}/actions/cancel", headers=admin_headers
    )
    assert response.status_code == 409


async def test_media_upload_and_delete(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    url = f"/api/v1/broadcasts/{created.json()['id']}/media"
    uploaded = await client.put(
        url, content=b"jpeg", headers={**admin_headers, "Content-Type": "image/jpeg"}
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["media_type"] == "PHOTO"
    deleted = await client.delete(url, headers=admin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["media_type"] is None


@pytest.mark.parametrize(("content_type", "status_code"), [("video/mp4", 200), ("image/png", 400)])
async def test_media_upload_takes_raw_body_up_to_type_limit(
    client: httpx.AsyncClient, admin_headers: dict[str, str], content_type: str, status_code: int
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    response = await client.put(
        f"/api/v1/broadcasts/{created.json()['id']}/media",
        content=b"\x00" * (12 * 1024 * 1024),
        headers={**admin_headers, "Content-Type": content_type},
    )
    assert response.status_code == status_code
    if status_code == 200:
        assert response.json()["media_type"] == "VIDEO"
    else:
        assert response.json()["code"] == "BROADCAST_MEDIA_INVALID"


async def test_media_upload_body_is_not_read_without_auth(
    config: AppConfig, test_container: AsyncContainer
) -> None:
    app = get_app(config)
    setup_dishka(test_container, app)
    pulled: list[int] = []

    async def counting(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        async def counted_receive():  # type: ignore[no-untyped-def]
            message = await receive()
            if message["type"] == "http.request":
                pulled.append(len(message.get("body", b"")))
            return message

        await app(scope, counted_receive, send)

    transport = httpx.ASGITransport(app=counting)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.put(
            "/api/v1/broadcasts/1/media",
            content=b"\x00" * (40 * 1024 * 1024),
            headers={"Content-Type": "video/mp4"},
        )
    assert response.status_code == 401
    assert pulled == []


async def test_delete_draft(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    url = f"/api/v1/broadcasts/{created.json()['id']}"
    assert (await client.delete(url, headers=admin_headers)).status_code == 204
    assert (await client.get(url, headers=admin_headers)).status_code == 404


async def test_update_non_draft_is_409(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    broadcast_repository: BroadcastRepository,
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    broadcast_id = created.json()["id"]
    await broadcast_repository.update_fields(broadcast_id, status=BroadcastStatus.COMPLETED)
    response = await client.put(
        f"/api/v1/broadcasts/{broadcast_id}", json=_body("Bye"), headers=admin_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BROADCAST_INVALID_STATUS"


async def test_list_recipients_shape(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    response = await client.get(
        f"/api/v1/broadcasts/{created.json()['id']}/recipients", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_summary_is_200(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/broadcasts/summary", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["by_status"]["DRAFT"] == 0
    assert response.json()["next_scheduled_at"] is None


async def test_list_accepts_repeated_status_and_search(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    body = _body()
    body["title"] = "Findable"
    await client.post("/api/v1/broadcasts", json=body, headers=admin_headers)
    response = await client.get(
        "/api/v1/broadcasts?status=DRAFT&status=FAILED&search=findable", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Findable"
    assert response.json()["items"][0]["created_by_name"] == "bcowner"
    none = await client.get("/api/v1/broadcasts?status=FAILED", headers=admin_headers)
    assert none.json()["total"] == 0


async def test_media_upload_without_the_permission_reads_no_body(
    config: AppConfig,
    test_container: AsyncContainer,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="bcnomedia",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="bcnomedia",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_revokes=["BROADCASTS_MEDIA_SET"],
            )
        )
        await uow.commit()
    token = await _issue_token(admin.id, session_repository, config)
    app = get_app(config)
    setup_dishka(test_container, app)
    pulled: list[int] = []

    async def counting(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        async def counted_receive():  # type: ignore[no-untyped-def]
            message = await receive()
            if message["type"] == "http.request":
                pulled.append(len(message.get("body", b"")))
            return message

        await app(scope, counted_receive, send)

    transport = httpx.ASGITransport(app=counting)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.put(
            "/api/v1/broadcasts/1/media",
            content=b"\x00" * (12 * 1024 * 1024),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"},
        )
    assert response.status_code == 403
    assert pulled == []


async def test_rejected_media_upload_leaves_no_temp_file(
    client: httpx.AsyncClient, admin_headers: dict[str, str], config: AppConfig
) -> None:
    created = await client.post("/api/v1/broadcasts", json=_body(), headers=admin_headers)
    response = await client.put(
        f"/api/v1/broadcasts/{created.json()['id']}/media",
        content=b"\x00" * (12 * 1024 * 1024),
        headers={**admin_headers, "Content-Type": "image/png"},
    )
    assert response.status_code == 400
    assert list((config.media_dir / "broadcasts").glob("*.part")) == []
