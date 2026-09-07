import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator, Iterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import BannerName, DialogFlow, Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.dialogs import catalog, get_dialogs_providers
from app.modules.dialogs.repository import DialogRepository
from app.modules.settings import get_settings_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto
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
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_blacklist_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        *get_dialogs_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _token_for(
    role: Role,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=f"dialogstest{role.value}",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=f"dialogstest{role.value}",
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{role.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    return create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    catalog._reset_for_tests()
    catalog.register_action_key("get_trial")
    catalog.bind_action_handler("get_trial", lambda: None)
    yield
    catalog._reset_for_tests()


async def test_list_windows_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/dialogs/windows")
    assert response.status_code == 401


async def test_get_catalog(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    response = await client.get(f"{API_V1}/dialogs/catalog", headers=headers)
    assert response.status_code == 200
    assert response.json()["action_keys"] == ["get_trial"]


async def test_owner_lists_and_updates(
    client: httpx.AsyncClient,
    dialog_repository: DialogRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    await dialog_repository.upsert_seed(
        "menu.main",
        DialogFlow.MENU,
        BannerName.MENU,
        {
            "banner_name": "menu",
            "buttons": [
                {
                    "key": "trial",
                    "text_key": "btn-menu.trial",
                    "row": 0,
                    "column": 0,
                    "link_type": "action",
                    "action_key": "get_trial",
                    "target_window_key": None,
                    "url_value": None,
                    "visibility_condition": None,
                    "style": None,
                    "icon_custom_emoji_id": None,
                    "is_hidden": False,
                }
            ],
        },
    )
    await uow.commit()

    list_response = await client.get(f"{API_V1}/dialogs/windows", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["key"] == "menu.main"

    get_response = await client.get(f"{API_V1}/dialogs/windows/menu.main", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["key"] == "menu.main"

    resp = await client.put(
        f"{API_V1}/dialogs/windows/menu.main",
        headers=headers,
        json={"banner_name": "default", "is_enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is False


async def test_get_window_missing_is_404(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    response = await client.get(f"{API_V1}/dialogs/windows/menu.ghost", headers=headers)
    assert response.status_code == 404


async def test_replace_buttons_bad_action_is_400(
    client: httpx.AsyncClient,
    dialog_repository: DialogRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    await dialog_repository.upsert_seed(
        "menu.main", DialogFlow.MENU, BannerName.MENU, {"banner_name": "menu", "buttons": []}
    )
    await uow.commit()

    resp = await client.put(
        f"{API_V1}/dialogs/windows/menu.main/buttons",
        headers=headers,
        json={
            "buttons": [
                {
                    "row": 0,
                    "column": 0,
                    "text_key": "x",
                    "link_type": "action",
                    "action_key": "ghost",
                }
            ]
        },
    )
    assert resp.status_code == 400


async def test_replace_buttons_overlong_text_key_is_422(
    client: httpx.AsyncClient,
    dialog_repository: DialogRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    await dialog_repository.upsert_seed(
        "menu.main", DialogFlow.MENU, BannerName.MENU, {"banner_name": "menu", "buttons": []}
    )
    await uow.commit()

    resp = await client.put(
        f"{API_V1}/dialogs/windows/menu.main/buttons",
        headers=headers,
        json={
            "buttons": [
                {
                    "row": 0,
                    "column": 0,
                    "text_key": "x" * 65,
                    "link_type": "action",
                    "action_key": "get_trial",
                }
            ]
        },
    )
    assert resp.status_code == 422


async def test_create_update_delete_custom_window(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    create_resp = await client.post(
        f"{API_V1}/dialogs/windows",
        headers=headers,
        json={"title_text": "Custom title"},
    )
    assert create_resp.status_code == 201
    key = create_resp.json()["key"]
    assert create_resp.json()["kind"] == "custom"

    delete_resp = await client.delete(f"{API_V1}/dialogs/windows/{key}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"{API_V1}/dialogs/windows/{key}", headers=headers)
    assert missing_resp.status_code == 404


async def test_delete_seed_window_is_400(
    client: httpx.AsyncClient,
    dialog_repository: DialogRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    await dialog_repository.upsert_seed(
        "menu.main", DialogFlow.MENU, BannerName.MENU, {"banner_name": "menu", "buttons": []}
    )
    await uow.commit()

    resp = await client.delete(f"{API_V1}/dialogs/windows/menu.main", headers=headers)
    assert resp.status_code == 400


async def test_delete_missing_window_is_404(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    resp = await client.delete(f"{API_V1}/dialogs/windows/menu.ghost", headers=headers)
    assert resp.status_code == 404


async def test_reset_window_and_reset_all(
    client: httpx.AsyncClient,
    dialog_repository: DialogRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    await dialog_repository.upsert_seed(
        "menu.main", DialogFlow.MENU, BannerName.MENU, {"banner_name": "menu", "buttons": []}
    )
    await uow.commit()

    await client.put(
        f"{API_V1}/dialogs/windows/menu.main",
        headers=headers,
        json={"is_enabled": False},
    )
    reset_resp = await client.post(f"{API_V1}/dialogs/windows/menu.main/reset", headers=headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["is_enabled"] is True

    reset_all_resp = await client.post(f"{API_V1}/dialogs/reset", headers=headers)
    assert reset_all_resp.status_code == 204


async def test_window_response_includes_text_keys_for_seed_window(
    client: httpx.AsyncClient,
    dialog_repository: DialogRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.text_keys_test",
            flow=DialogFlow.MENU,
            text_keys=("msg-text-keys-test",),
            banner_name=None,
        )
    )
    await dialog_repository.upsert_seed(
        "menu.text_keys_test", DialogFlow.MENU, None, {"banner_name": None, "buttons": []}
    )
    await uow.commit()

    response = await client.get(f"{API_V1}/dialogs/windows/menu.text_keys_test", headers=headers)
    assert response.status_code == 200
    assert response.json()["text_keys"] == ["msg-text-keys-test"]


async def test_window_response_includes_text_keys_for_custom_window(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    create_resp = await client.post(
        f"{API_V1}/dialogs/windows",
        headers=headers,
        json={"title_text": "Custom title"},
    )
    assert create_resp.status_code == 201
    key = create_resp.json()["key"]
    assert create_resp.json()["text_keys"] == [f"msg-dialog-{key}"]


async def test_update_dialog_text_requires_permission(
    client: httpx.AsyncClient, settings_repository, translations_repository
) -> None:
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "msg-router-test", "", "Hi!")

    response = await client.put(
        f"{API_V1}/dialogs/text/en/msg-router-test", json={"value": "Hi there!"}
    )
    assert response.status_code == 401


async def test_update_dialog_text_updates_value(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    settings_repository,
    translations_repository,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.router_text",
            flow=DialogFlow.MENU,
            text_keys=("msg-router-window-text",),
            banner_name=None,
        )
    )
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "msg-router-window-text", "", "Hi!")

    response = await client.put(
        f"{API_V1}/dialogs/text/en/msg-router-window-text",
        json={"value": "Hi there!"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["value"] == "Hi there!"


async def test_update_dialog_text_missing_key_is_404(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    settings_repository,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.router_ghost",
            flow=DialogFlow.MENU,
            text_keys=("msg-router-ghost-text",),
            banner_name=None,
        )
    )
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)

    response = await client.put(
        f"{API_V1}/dialogs/text/en/msg-router-ghost-text",
        json={"value": "Hi there!"},
        headers=headers,
    )
    assert response.status_code == 404
