import httpx
import pytest
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.modules.auth.repository import SessionRepository
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import BotSignInGrantDto, InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.usecases import IssueBotSignInLinkUseCase
from app.modules.settings.dto import UpdateBotSettingsDto, UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.identity_links.conftest import bearer

LINK_DEEPLINK = f"{API_V1}/users/me/identities/telegram/deeplink"
LINK_SIGNIN = f"{API_V1}/users/me/identities/telegram/signin"
_PROFILE = TelegramProfileDto(telegram_id=8118, name="Ann", username="ann", language="en")


@pytest.fixture
def store(redis: Redis) -> DeeplinkStore:
    return DeeplinkStore(redis)


@pytest.fixture
async def telegram_enabled(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_enabled=True)
        )
        await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="1:abc"))


@pytest.fixture
async def me(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="me", email="me@gmail.com"))


@pytest.fixture
async def headers(
    me: UserDto, session_repository: SessionRepository, config: AppConfig
) -> dict[str, str]:
    return await bearer(me.id, session_repository, config)


@pytest.mark.usefixtures("telegram_enabled")
async def test_link_free_telegram(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    config: AppConfig,
    store: DeeplinkStore,
    user_repository: UserRepository,
    me: UserDto,
    headers: dict[str, str],
) -> None:
    async def _username(token: str, proxy: object) -> str:
        return "shop_bot"

    monkeypatch.setattr(
        "app.modules.cabinet_auth.usecases.request_deeplink.fetch_bot_username", _username
    )
    monkeypatch.setattr(config, "web_cabinet_url", "https://cabinet.example.com")

    response = await client.post(LINK_DEEPLINK, headers=headers)
    assert response.status_code == 200
    start = response.json()["bot_url"].rsplit("webauth_", 1)[1]
    ticket = await store.peek(start)
    assert ticket is not None and ticket.link_user_id == me.id

    url = await IssueBotSignInLinkUseCase(store, config).execute(start, _PROFILE)
    assert url is not None and url.startswith("https://cabinet.example.com/link/bot#token=")

    done = await client.post(
        LINK_SIGNIN, json={"token": url.split("token=", 1)[1]}, headers=headers
    )
    assert done.status_code == 200
    assert done.json()["status"] == "linked"
    linked = await user_repository.find_by_id(me.id)
    assert linked is not None and linked.telegram_id == _PROFILE.telegram_id


@pytest.mark.usefixtures("telegram_enabled")
async def test_link_signin_rejects_login_grant(
    client: httpx.AsyncClient, store: DeeplinkStore, headers: dict[str, str]
) -> None:
    token = await store.issue_signin(BotSignInGrantDto(profile=_PROFILE, codes=InviteCodesDto()))
    response = await client.post(LINK_SIGNIN, json={"token": token}, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "DEEPLINK_EXPIRED"


@pytest.mark.usefixtures("telegram_enabled")
async def test_link_signin_other_user_rejected(
    client: httpx.AsyncClient, store: DeeplinkStore, me: UserDto, headers: dict[str, str]
) -> None:
    token = await store.issue_signin(
        BotSignInGrantDto(profile=_PROFILE, codes=InviteCodesDto(), link_user_id=me.id + 1000)
    )
    response = await client.post(LINK_SIGNIN, json={"token": token}, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "DEEPLINK_EXPIRED"


async def test_link_routes_need_a_session(client: httpx.AsyncClient) -> None:
    assert (await client.post(LINK_DEEPLINK)).status_code == 401
    assert (await client.post(LINK_SIGNIN, json={"token": "x" * 43})).status_code == 401
