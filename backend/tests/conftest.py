import os

# Tests run against the local dev Postgres/Redis containers, so the
# docker-service hostnames the real app expects are overridden here.
# Everything else (secrets, remnawave/bot tokens) comes from the repo-root .env.
#
# Must run before the imports below: app.core.broker builds its broker at
# import time from AppConfig.get().redis.dsn, and with the docker hostname
# every .kiq() waits ~5s on DNS before publish() swallows the error.
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
# the test client talks plain http to testserver: a Secure cookie never comes back
os.environ.setdefault("APP_SECURE_COOKIES", "false")

from decimal import Decimal
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import ContainerMiddleware
from fastapi import FastAPI
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.core.ports import EventPublisher
from app.modules.advertising.repository import AdLinkRepository
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.repository import SessionRepository
from app.modules.banners.repository import BannerRepository
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.dialogs.repository import DialogRepository
from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.gateways.repository import GatewayRepository
from app.modules.legal.repository import LegalRepository
from app.modules.notifications.repository import NotificationRepository
from app.modules.oauth.providers.state_store import OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.passkeys.challenge_store import PasskeyChallengeStore
from app.modules.passkeys.repository import PasskeyRepository
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import repository as pricing_repository_module
from app.modules.pricing.repository import PricingRepository
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.translations.repository import TranslationRepository
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.fakes.container import make_test_container
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.remnawave import FakeHwidStore, FakeUserStore, make_fake_remnawave_transport
from tests.modules.subscriptions.factories import make_eligibility


@pytest.fixture
def config() -> AppConfig:
    return AppConfig.get()


@pytest.fixture(scope="session")
def api_app() -> FastAPI:
    # get_app costs ~0.4 s; a test binds its own container through
    # app.state.dishka_container, which ContainerMiddleware reads per request
    app = get_app(AppConfig.get())
    app.add_middleware(ContainerMiddleware)
    return app


@pytest.fixture(autouse=True)
async def _clean_redis(config: AppConfig) -> AsyncIterator[None]:
    # Redis state (rate-limit counters, oauth state, the webhook replay guard)
    # isn't rolled back like `session` and would outlive the test; the
    # container is test-only, so flushing it whole is safe.
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    await client.flushdb()
    try:
        yield
    finally:
        await client.aclose()


@pytest.fixture
async def engine(config: AppConfig) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(config.database.dsn)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    # Each test runs inside a connection-level transaction that's rolled back
    # afterwards, so tests never leave data behind or depend on each other.
    # session.commit() inside the code under test only closes a SAVEPOINT.
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async_session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield async_session
        await async_session.close()
        await transaction.rollback()


@pytest.fixture
def broadcast_repository(session: AsyncSession) -> BroadcastRepository:
    return BroadcastRepository(session)


@pytest.fixture
def user_repository(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


@pytest.fixture
def user_stats_repository(session: AsyncSession) -> UserStatsRepository:
    return UserStatsRepository(session)


@pytest.fixture
def user_blacklist_repository(session: AsyncSession) -> UserBlacklistRepository:
    return UserBlacklistRepository(session)


@pytest.fixture
def oauth_identity_repository(session: AsyncSession) -> OAuthIdentityRepository:
    return OAuthIdentityRepository(session)


@pytest.fixture
def passkey_repository(session: AsyncSession) -> PasskeyRepository:
    return PasskeyRepository(session)


@pytest.fixture
def session_repository(session: AsyncSession) -> SessionRepository:
    return SessionRepository(session)


@pytest.fixture
def uow(session: AsyncSession) -> UnitOfWork:
    return UnitOfWork(session)


@pytest.fixture
def event_publisher(uow: UnitOfWork) -> EventPublisher:
    return OutboxEventPublisher(uow, RecordingDispatch())


@pytest.fixture
def ad_link_repository(session: AsyncSession) -> AdLinkRepository:
    return AdLinkRepository(session)


@pytest.fixture
def settings_repository(session: AsyncSession) -> SettingsRepository:
    return SettingsRepository(session)


@pytest.fixture
def pricing_repository(session: AsyncSession) -> PricingRepository:
    return PricingRepository(session)


@pytest.fixture(autouse=True)
def _unit_seed_rates(monkeypatch: pytest.MonkeyPatch) -> None:
    # Revenue/ROI tests aggregate across currencies and assume 1:1 cross rates;
    # keeps them independent of the production seed (RUB 85, XTR 77).
    seed = pricing_repository_module._SEED_RATES
    unit = {currency: (Decimal("1"), *rest) for currency, (_, *rest) in seed.items()}
    monkeypatch.setattr(pricing_repository_module, "_SEED_RATES", unit)


@pytest.fixture
def subscription_repository(session: AsyncSession) -> SubscriptionRepository:
    return SubscriptionRepository(session)


@pytest.fixture
def addon_repository(session: AsyncSession) -> AddOnRepository:
    return AddOnRepository(session)


@pytest.fixture
def idempotency_repository(session: AsyncSession) -> PurchaseIdempotencyRepository:
    return PurchaseIdempotencyRepository(session)


@pytest.fixture
def subscription_stats_repository(session: AsyncSession) -> SubscriptionStatsRepository:
    return SubscriptionStatsRepository(session)


@pytest.fixture
def purchase_subscription_use_case(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    pricing_repository: PricingRepository,
) -> PurchaseSubscriptionUseCase:
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        pricing_repository,
        PurchaseIdempotencyRepository(subscription_repository.session),
        UserRepository(subscription_repository.session),
    )


@pytest.fixture
def api_token_repository(session: AsyncSession) -> ApiTokenRepository:
    return ApiTokenRepository(session)


@pytest.fixture
def announcement_repository(session: AsyncSession) -> AnnouncementRepository:
    return AnnouncementRepository(session)


@pytest.fixture
def banner_repository(session: AsyncSession) -> BannerRepository:
    return BannerRepository(session)


@pytest.fixture
def legal_repository(session: AsyncSession) -> LegalRepository:
    return LegalRepository(session)


@pytest.fixture
def emoji_pack_repository(session: AsyncSession) -> EmojiPackRepository:
    return EmojiPackRepository(session)


@pytest.fixture
def plan_repository(session: AsyncSession) -> PlanRepository:
    return PlanRepository(session)


@pytest.fixture
def promocode_repository(session: AsyncSession) -> PromocodeRepository:
    return PromocodeRepository(session)


@pytest.fixture
def event_log_repository(session: AsyncSession) -> EventLogRepository:
    return EventLogRepository(session)


@pytest.fixture
def notification_repository(session: AsyncSession) -> NotificationRepository:
    return NotificationRepository(session)


@pytest.fixture
def gateway_repository(session: AsyncSession) -> GatewayRepository:
    return GatewayRepository(session)


@pytest.fixture
def translation_repository(session: AsyncSession) -> TranslationRepository:
    return TranslationRepository(session)


@pytest.fixture
def referral_repository(session: AsyncSession) -> ReferralRepository:
    return ReferralRepository(session)


@pytest.fixture
def blacklist_repository(session: AsyncSession) -> BlacklistRepository:
    return BlacklistRepository(session)


@pytest.fixture
def dialog_repository(session: AsyncSession) -> DialogRepository:
    return DialogRepository(session)


@pytest.fixture
async def redis(config: AppConfig) -> AsyncIterator[Redis]:
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def oauth_state_store(redis: Redis) -> OAuthStateStore:
    return OAuthStateStore(redis)


@pytest.fixture
def redis_challenge_store(redis: Redis) -> PasskeyChallengeStore:
    return PasskeyChallengeStore(redis)


@pytest.fixture
def remnawave_store() -> FakeUserStore:
    return {}


@pytest.fixture
def remnawave_hwid_store() -> FakeHwidStore:
    return {}


@pytest.fixture
def remnawave_sdk(
    remnawave_store: FakeUserStore, remnawave_hwid_store: FakeHwidStore
) -> RemnawaveSDK:
    transport, _, _ = make_fake_remnawave_transport(remnawave_store, remnawave_hwid_store)
    client = httpx.AsyncClient(transport=transport, base_url="http://fake-panel.test/api")
    return RemnawaveSDK(client=client)


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config)
    yield container
    await container.close()
