import httpx
import pytest
from dishka import AsyncContainer
from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.usecases import ConfirmDeeplinkUseCase, PollDeeplinkUseCase
from app.modules.settings.dto import UpdateBotSettingsDto, UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository

_IP = "203.0.113.1"


@pytest.fixture
async def deeplink_store(redis: Redis) -> DeeplinkStore:
    return DeeplinkStore(redis)


@pytest.fixture
async def poll(container: AsyncContainer):  # type: ignore[no-untyped-def]
    async with container() as request_container:
        yield await request_container.get(PollDeeplinkUseCase)


@pytest.fixture
async def confirm(container: AsyncContainer):  # type: ignore[no-untyped-def]
    async with container() as request_container:
        yield await request_container.get(ConfirmDeeplinkUseCase)


async def test_confirmed_token_signs_in_only_with_binding(
    deeplink_store: DeeplinkStore, poll: PollDeeplinkUseCase, confirm: ConfirmDeeplinkUseCase
) -> None:
    token, binding = await deeplink_store.create(InviteCodesDto(referral_code="abc"), _IP, "ua")
    assert await poll.execute(binding, _IP, "ua") is None

    profile = TelegramProfileDto(telegram_id=7007, name="Ann", username=None, language="en")
    assert await confirm.execute(token, profile) is True
    assert await confirm.execute(token, profile) is False

    with pytest.raises(AuthenticationError):
        await poll.execute("other-binding", _IP, "ua")

    signed_in = await poll.execute(binding, _IP, "ua")
    assert signed_in is not None
    user, issued = signed_in
    assert user.telegram_id == 7007 and issued.access_token

    with pytest.raises(AuthenticationError) as error:
        await poll.execute(binding, _IP, "ua")
    assert error.value.code is ErrorCode.DEEPLINK_EXPIRED


async def test_peek_sees_only_pending_codes(
    deeplink_store: DeeplinkStore, confirm: ConfirmDeeplinkUseCase
) -> None:
    token, _ = await deeplink_store.create(InviteCodesDto(referral_code="abc"), _IP, "ua")
    pending = await deeplink_store.peek(token)
    assert pending is not None and pending.codes.referral_code == "abc"
    await confirm.execute(
        token, TelegramProfileDto(telegram_id=1, name="A", username=None, language=None)
    )
    assert await deeplink_store.peek(token) is None
    assert await deeplink_store.peek("unknown") is None


async def test_poll_without_cookie_is_expired(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/cabinet/auth/telegram/deeplink/poll")
    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.DEEPLINK_EXPIRED.value


_BASE = "/api/v1/cabinet/auth/telegram/deeplink"


async def test_deeplink_routes_end_to_end(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    deeplink_store: DeeplinkStore,
    confirm: ConfirmDeeplinkUseCase,
) -> None:
    async def _username(token: str, proxy: object) -> str:
        return "shop_bot"

    monkeypatch.setattr(
        "app.modules.cabinet_auth.usecases.request_deeplink.fetch_bot_username", _username
    )
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_enabled=True)
        )
        await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="1:abc"))

    response = await client.post(_BASE, json={})
    assert response.status_code == 200
    body = response.json()
    assert body["bot_url"].startswith("https://t.me/shop_bot?start=webauth_")
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.cookies.get("cabinet_webauth")

    poll = await client.post(f"{_BASE}/poll")
    assert poll.status_code == 202 and poll.json() == {"status": "pending"}

    token = body["bot_url"].rsplit("webauth_", 1)[1]
    profile = TelegramProfileDto(telegram_id=7117, name="Ann", username=None, language="en")
    assert await confirm.execute(token, profile) is True

    done = await client.post(f"{_BASE}/poll")
    assert done.status_code == 200 and done.json()["access_token"]
    assert client.cookies.get("cabinet_refresh_token")
    assert not client.cookies.get("cabinet_webauth")
