import httpx
import pytest
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.usecases import IssueBotSignInLinkUseCase
from app.modules.settings.dto import UpdateBotSettingsDto, UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository

_IP = "203.0.113.1"
_BASE = "/api/v1/auth/telegram/deeplink"
_SIGNIN = "/api/v1/auth/telegram/signin"


@pytest.fixture
async def deeplink_store(redis: Redis) -> DeeplinkStore:
    return DeeplinkStore(redis)


async def test_peek_reads_the_start_record_without_spending_it(
    deeplink_store: DeeplinkStore,
) -> None:
    token = await deeplink_store.create(InviteCodesDto(referral_code="abc"))
    ticket = await deeplink_store.peek(token)
    assert ticket is not None and ticket.codes.referral_code == "abc"
    assert await deeplink_store.peek(token) is not None
    assert await deeplink_store.peek("unknown") is None


async def test_signin_with_unknown_token_is_expired(
    client: httpx.AsyncClient, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_deeplink_enabled=True)
        )
    response = await client.post(_SIGNIN, json={"token": "x" * 43})
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.DEEPLINK_EXPIRED.value


async def test_deeplink_then_bot_link_signs_in_once(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    deeplink_store: DeeplinkStore,
    config: AppConfig,
) -> None:
    async def _username(token: str, proxy: object) -> str:
        return "shop_bot"

    monkeypatch.setattr(
        "app.modules.cabinet_auth.usecases.request_deeplink.fetch_bot_username", _username
    )
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_deeplink_enabled=True)
        )
        await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="1:abc"))

    response = await client.post(_BASE, json={"ref": "abc"})
    assert response.status_code == 200
    assert response.json()["bot_url"].startswith("https://t.me/shop_bot?start=webauth_")
    start = response.json()["bot_url"].rsplit("webauth_", 1)[1]

    # the start token is public (it sits in a t.me URL) and never signs anybody in
    rejected = await client.post(_SIGNIN, json={"token": start})
    assert rejected.status_code == 401

    profile = TelegramProfileDto(telegram_id=7117, name="Ann", username=None, language="en")
    link = await IssueBotSignInLinkUseCase(deeplink_store, config).execute(start, profile)
    assert link is not None
    signin = link.url.split("token=", 1)[1]

    # the link sent to another browser (one without the binding cookie) is refused there
    async with httpx.AsyncClient(transport=client._transport, base_url=client.base_url) as other:
        elsewhere = await other.post(_SIGNIN, json={"token": signin})
    assert elsewhere.status_code == 401
    assert elsewhere.json()["code"] == ErrorCode.DEEPLINK_OTHER_BROWSER.value
    assert client.cookies.get("deeplink_binding")

    # ...and stays usable in the browser that asked for it
    done = await client.post(_SIGNIN, json={"token": signin})
    assert done.status_code == 200 and done.json()["access_token"]
    assert client.cookies.get("cabinet_refresh_token")

    again = await client.post(_SIGNIN, json={"token": signin})
    assert again.status_code == 401
    assert again.json()["code"] == ErrorCode.DEEPLINK_EXPIRED.value
