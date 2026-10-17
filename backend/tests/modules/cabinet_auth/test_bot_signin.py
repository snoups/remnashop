import pytest
from dishka import AsyncContainer
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import BotSignInGrantDto, InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.usecases import BotSignInUseCase, IssueBotSignInLinkUseCase
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository

_IP = "203.0.113.1"
_CABINET = "https://cabinet.example.com"
_PROFILE = TelegramProfileDto(telegram_id=7007, name="Ann", username="ann", language="en")


@pytest.fixture
def store(redis: Redis) -> DeeplinkStore:
    return DeeplinkStore(redis)


@pytest.fixture
async def telegram_enabled(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_enabled=True)
        )


@pytest.fixture
async def sign_in_use_case(container: AsyncContainer):  # type: ignore[no-untyped-def]
    async with container() as request_container:
        yield await request_container.get(BotSignInUseCase)


def _token_from(url: str) -> str:
    return url.split("token=", 1)[1]


async def test_start_record_is_taken_once(store: DeeplinkStore) -> None:
    token = await store.create(InviteCodesDto(referral_code="abc"))
    first = await store.take_start(token)
    assert first is not None and first.codes.referral_code == "abc"
    assert await store.take_start(token) is None
    assert await store.peek(token) is None


async def test_signin_token_is_single_use(store: DeeplinkStore) -> None:
    token = await store.issue_signin(BotSignInGrantDto(profile=_PROFILE, codes=InviteCodesDto()))
    grant = await store.take_signin(token)
    assert grant is not None and grant.profile == _PROFILE
    assert await store.take_signin(token) is None
    assert await store.take_signin("unknown") is None


async def test_issue_link_builds_a_cabinet_url_and_consumes_the_start(
    store: DeeplinkStore, config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", f"{_CABINET}/")
    start = await store.create(InviteCodesDto(ad_link_code="ad1"))
    issue = IssueBotSignInLinkUseCase(store, config)

    link = await issue.execute(start, _PROFILE)

    assert link is not None and not link.is_link
    assert link.url.startswith(f"{_CABINET}/login/bot#token=")
    signin = _token_from(link.url)
    assert signin != start
    grant = await store.take_signin(signin)
    assert grant is not None and grant.codes.ad_link_code == "ad1"
    # the same start link can't mint a second sign-in token
    assert await issue.execute(start, _PROFILE) is None


async def test_issue_link_without_cabinet_url_gives_nothing(
    store: DeeplinkStore, config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", "  ")
    start = await store.create(InviteCodesDto())
    assert await IssueBotSignInLinkUseCase(store, config).execute(start, _PROFILE) is None


@pytest.mark.usefixtures("telegram_enabled")
async def test_signin_signs_in_once(
    store: DeeplinkStore, sign_in_use_case: BotSignInUseCase
) -> None:
    token = await store.issue_signin(BotSignInGrantDto(profile=_PROFILE, codes=InviteCodesDto()))

    user, issued = await sign_in_use_case.execute(token, _IP, "ua")
    assert user.telegram_id == 7007 and issued.access_token

    with pytest.raises(AuthenticationError) as error:
        await sign_in_use_case.execute(token, _IP, "ua")
    assert error.value.code is ErrorCode.DEEPLINK_EXPIRED


async def test_signin_is_refused_when_telegram_is_disabled(
    store: DeeplinkStore, sign_in_use_case: BotSignInUseCase
) -> None:
    token = await store.issue_signin(BotSignInGrantDto(profile=_PROFILE, codes=InviteCodesDto()))
    with pytest.raises(AuthenticationError) as error:
        await sign_in_use_case.execute(token, _IP, "ua")
    assert error.value.code is ErrorCode.CABINET_TELEGRAM_DISABLED
    # a switched-off method must not burn the link: switching it back on lets it through
    assert await store.take_signin(token) is not None


async def test_link_token_url_uses_link_path(
    store: DeeplinkStore, config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", _CABINET)
    start = await store.create(InviteCodesDto(), link_user_id=42)
    ticket = await store.peek(start)
    assert ticket is not None and ticket.link_user_id == 42

    link = await IssueBotSignInLinkUseCase(store, config).execute(start, _PROFILE)

    assert link is not None and link.is_link
    assert link.url.startswith(f"{_CABINET}/link/bot#token=")
    grant = await store.take_signin(_token_from(link.url))
    assert grant is not None and grant.link_user_id == 42 and grant.profile == _PROFILE


@pytest.mark.usefixtures("telegram_enabled")
async def test_login_signin_rejects_link_grant(
    store: DeeplinkStore, sign_in_use_case: BotSignInUseCase
) -> None:
    token = await store.issue_signin(
        BotSignInGrantDto(profile=_PROFILE, codes=InviteCodesDto(), link_user_id=42)
    )
    with pytest.raises(AuthenticationError) as error:
        await sign_in_use_case.execute(token, _IP, "ua")
    assert error.value.code is ErrorCode.DEEPLINK_EXPIRED
