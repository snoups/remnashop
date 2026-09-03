import os

# Tests run against the local Postgres/Redis containers used for local dev (see
# CLAUDE.md) -- override the docker-service hostnames the real app expects.
# Everything else (secrets, remnawave/bot tokens) comes from the repo-root
# .env, same as any other local run.
#
# This MUST run before any import below: app.modules.promocodes.repository
# transitively imports app.worker.broker, which builds its ListQueueBroker
# singleton at import time from AppConfig.get().redis.dsn. Import it after
# the overrides and that singleton bakes in the docker-internal Redis
# hostname for the rest of the pytest session -- every OutboxEventPublisher
# .kiq() call then spends ~5s failing DNS resolution before the
# contextlib.suppress in publish() swallows it, which is where a ~14min
# full suite came from despite nothing being actually broken.
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

from typing import AsyncIterator

import httpx
import pytest
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.core.ports import EventPublisher
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.repository import SessionRepository
from app.modules.banners.repository import BannerRepository
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.gateways.repository import GatewaysRepository
from app.modules.oauth.providers.state_store import OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.translations.repository import TranslationsRepository
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeHwidStore, FakeUserStore, make_fake_remnawave_transport


@pytest.fixture
def config() -> AppConfig:
    return AppConfig.get()


@pytest.fixture(autouse=True)
async def _clean_redis(config: AppConfig) -> AsyncIterator[None]:
    # Unlike `session` (rolled back per test), Redis state from one test --
    # rate-limit counters, oauth state, the webhook replay guard -- has no
    # equivalent cleanup and would otherwise persist (by TTL) across tests
    # and even separate pytest invocations. Dedicated test-only container
    # (see the REDIS_HOST/REDIS_PORT override above), safe to flush wholesale.
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
def user_repository(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


@pytest.fixture
def oauth_identity_repository(session: AsyncSession) -> OAuthIdentityRepository:
    return OAuthIdentityRepository(session)


@pytest.fixture
def session_repository(session: AsyncSession) -> SessionRepository:
    return SessionRepository(session)


@pytest.fixture
def uow(session: AsyncSession) -> UnitOfWork:
    return UnitOfWork(session)


@pytest.fixture
def event_publisher(session: AsyncSession) -> EventPublisher:
    return OutboxEventPublisher(session)


@pytest.fixture
def settings_repository(session: AsyncSession) -> SettingsRepository:
    return SettingsRepository(session)


@pytest.fixture
def pricing_repository(session: AsyncSession) -> PricingRepository:
    return PricingRepository(session)


@pytest.fixture
def subscription_repository(session: AsyncSession) -> SubscriptionRepository:
    return SubscriptionRepository(session)


@pytest.fixture
def addon_repository(session: AsyncSession) -> AddOnRepository:
    return AddOnRepository(session)


@pytest.fixture
def api_token_repository(session: AsyncSession) -> ApiTokenRepository:
    return ApiTokenRepository(session)


@pytest.fixture
def banner_repository(session: AsyncSession) -> BannerRepository:
    return BannerRepository(session)


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
def gateways_repository(session: AsyncSession) -> GatewaysRepository:
    return GatewaysRepository(session)


@pytest.fixture
def translations_repository(session: AsyncSession) -> TranslationsRepository:
    return TranslationsRepository(session)


@pytest.fixture
def referral_repository(session: AsyncSession) -> ReferralRepository:
    return ReferralRepository(session)


@pytest.fixture
def blacklist_repository(session: AsyncSession) -> BlacklistRepository:
    return BlacklistRepository(session)


@pytest.fixture
async def redis(config: AppConfig) -> AsyncIterator[Redis]:
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def oauth_state_store(redis: Redis) -> OAuthStateStore:
    return OAuthStateStore(redis)


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
