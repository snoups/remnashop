import asyncio
import json
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Optional, cast

import pytest
from cryptography.fernet import Fernet
from remnapy import RemnawaveSDK
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.cli.legacy import migrate as migrate_module
from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.migrate import MigrationResult, migrate, preflight, upgrade_legacy_schema
from app.cli.legacy.panel import PanelIndex
from app.cli.legacy.schema import LEGACY_HEAD, current_revision
from app.core.config import AppConfig
from app.core.db.models import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.core.security import verify_password
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.usecases import BootstrapOwnerUseCase
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch

LegacyAt = Callable[[AsyncEngine, str], Awaitable[None]]

_SNAPSHOT: dict[str, Any] = {
    "id": 1,
    "tag": None,
    "name": "Basic",
    "type": "BOTH",
    "duration": 30,
    "is_trial": False,
    "device_limit": 3,
    "traffic_limit": 100,
    "external_squad": None,
    "internal_squads": [],
    "traffic_limit_strategy": "NO_RESET",
}
_JSON_DEFAULTS: str = "'{}'::jsonb"
_OWNER_PASSWORD: str = "Sup3rSecretPassw0rd1234567890"
_INDEX = PanelIndex(
    by_short_uuid={"short1": 501, "short2": 502, "short3": 502, "short4": 503},
)


def _crypt_key(config: AppConfig) -> str:
    return config.crypt_key.get_secret_value()


def _enc(value: str, key: str) -> str:
    return "enc_" + Fernet(key.encode()).encrypt(value.encode()).decode()


async def _exec(connection: AsyncConnection, sql: str, **params: Any) -> None:
    await connection.execute(text(sql), params)


async def _seed_settings(connection: AsyncConnection) -> None:
    access = json.dumps({"mode": "PUBLIC", "purchases_allowed": True, "registration_allowed": True})
    requirements = json.dumps(
        {"channel_id": None, "channel_link": None, "rules_link": None, "channel_required": False}
    )
    await _exec(
        connection,
        "INSERT INTO settings (default_currency, access, requirements, notifications, menu, "
        f"backup, blacklist) VALUES ('RUB', CAST(:access AS jsonb), CAST(:req AS jsonb), "
        f"{_JSON_DEFAULTS}, {_JSON_DEFAULTS}, {_JSON_DEFAULTS}, {_JSON_DEFAULTS})",
        access=access,
        req=requirements,
    )


async def _seed_user(
    connection: AsyncConnection, user_id: int, *, role: str = "USER", **extra: Any
) -> None:
    await _exec(
        connection,
        "INSERT INTO users (id, telegram_id, username, name, role, language, personal_discount, "
        "purchase_discount, is_blocked, is_bot_blocked, referral_code, points, is_rules_accepted, "
        "is_trial_available, is_email_verified, auth_type, token_version, "
        "password_reset_attempts) VALUES (:id, :tg, :username, :name, "
        "CAST(:role AS user_role), 'RU', 0, 0, false, false, :code, 0, true, true, false, "
        "'telegram', 0, 0)",
        id=user_id,
        tg=1000 + user_id,
        username=extra.get("username"),
        name=f"user{user_id}",
        role=role,
        code=f"CODE{user_id}",
    )


async def _seed_head(connection: AsyncConnection, crypt_key: str) -> None:
    await _seed_settings(connection)
    await _exec(
        connection,
        "INSERT INTO plans (id, order_index, is_active, type, availability, name, traffic_limit, "
        "device_limit, internal_squads, is_trial, public_code) VALUES (1, 1, true, 'BOTH', "
        "'ALL', 'Basic', 100, 3, '{}', false, 'basic')",
    )
    await _exec(
        connection, "INSERT INTO plan_durations (id, days, plan_id, order_index) VALUES (1,30,1,1)"
    )
    await _exec(
        connection,
        "INSERT INTO plan_prices (id, currency, price, plan_duration_id) "
        "VALUES (1, 'RUB', 100, 1), (2, 'USD', 2, 1)",
    )
    await _seed_user(connection, 1, role="OWNER", username="boss")
    await _seed_user(connection, 2)
    await _seed_user(connection, 3)
    for sub_id, user_id in ((1, 1), (2, 2), (3, 2), (4, 3)):
        await _exec(
            connection,
            "INSERT INTO subscriptions (id, user_remna_id, status, is_trial, traffic_limit, "
            "device_limit, internal_squads, expire_at, url, plan_snapshot, "
            "traffic_limit_strategy, user_id) VALUES (:id, gen_random_uuid(), 'ACTIVE', false, "
            "100, 3, '{}', now() + interval '30 days', :url, CAST(:snapshot AS jsonb), "
            "'NO_RESET', :user_id)",
            id=sub_id,
            url=f"https://sub.example/s/short{sub_id}",
            snapshot=json.dumps(_SNAPSHOT),
            user_id=user_id,
        )
    for user_id, sub_id in ((1, 1), (2, 3), (3, 4)):
        await _exec(
            connection,
            "UPDATE users SET current_subscription_id = :sub WHERE id = :id",
            sub=sub_id,
            id=user_id,
        )
    pricing = json.dumps({"original_amount": "100", "final_amount": "100", "discount_percent": 0})
    for tx_id, user_id in ((1, 1), (2, 2), (3, 3)):
        await _exec(
            connection,
            "INSERT INTO transactions (id, payment_id, status, is_test, purchase_type, "
            "gateway_type, pricing, currency, plan_snapshot, user_id) VALUES (:id, "
            "gen_random_uuid(), 'COMPLETED', false, 'NEW', 'YOOKASSA', CAST(:pricing AS jsonb), "
            "'RUB', CAST(:snapshot AS jsonb), :user_id)",
            id=tx_id,
            pricing=pricing,
            snapshot=json.dumps(_SNAPSHOT),
            user_id=user_id,
        )
    await _seed_gateway(connection, _enc("secret", crypt_key))
    await _seed_extras(connection)


async def _seed_extras(connection: AsyncConnection) -> None:
    await _exec(connection, "INSERT INTO ad_links (id, name, code) VALUES (7, 'Ads', 'ads')")
    await _exec(connection, "UPDATE users SET ad_link_id = 7 WHERE id = 2")
    await _exec(
        connection,
        "INSERT INTO referrals (id, level, referrer_id, referred_id) VALUES (5, 'FIRST', 1, 2)",
    )
    await _exec(
        connection,
        "INSERT INTO referral_rewards (id, referral_id, type, amount, is_issued, user_id) "
        "VALUES (8, 5, 'EXTRA_DAYS', 30, true, 1), (9, 5, 'EXTRA_DAYS', 30, false, 1)",
    )
    await _exec(
        connection,
        "INSERT INTO promocodes (id, code, is_active, reward_type, reward, availability) "
        "VALUES (3, 'GIFT', true, 'DURATION', 7, 'ALL')",
    )
    await _exec(
        connection,
        "INSERT INTO promocode_activations (id, promocode_id, user_id) VALUES (4, 3, 3)",
    )
    await _exec(
        connection,
        "INSERT INTO user_oauth_providers (id, user_id, provider, provider_id) "
        "VALUES (6, 3, 'google', 'g-1'), (7, 3, 'vk', 'v-1')",
    )


async def _seed_gateway(connection: AsyncConnection, api_key: str) -> None:
    settings = json.dumps({"type": "YOOKASSA", "api_key": api_key, "shop_id": "1"})
    await _exec(
        connection,
        "INSERT INTO payment_gateways (id, order_index, type, currency, is_active, settings) "
        "VALUES (1, 1, 'YOOKASSA', 'RUB', true, CAST(:settings AS jsonb))",
        settings=settings,
    )


async def _prepare(engine: AsyncEngine, legacy_at: LegacyAt, crypt_key: str) -> None:
    await legacy_at(engine, LEGACY_HEAD)
    async with engine.begin() as connection:
        await _seed_head(connection, crypt_key)


async def _run(engine: AsyncEngine, config: AppConfig, **extra: Any) -> MigrationResult:
    return await migrate(
        engine,
        panel_index=_INDEX,
        crypt_key=_crypt_key(config),
        bot_owner_id=None,
        original_revision=LEGACY_HEAD,
        **extra,
    )


async def _ids(connection: AsyncConnection, table: str) -> list[int]:
    rows = await connection.scalars(text(f"SELECT id FROM {table} ORDER BY id"))
    return list(rows)


async def _legacy_schema_exists(connection: AsyncConnection) -> bool:
    return bool(
        await connection.scalar(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'legacy'")
        )
    )


def _panel(version: str = "3.0.0") -> RemnawaveSDK:
    async def get_metadata() -> Any:
        return SimpleNamespace(version=version)

    return cast(RemnawaveSDK, SimpleNamespace(system=SimpleNamespace(get_metadata=get_metadata)))


async def test_migrates_core_tables_with_ids(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    result = await _run(legacy_engine, config)

    async with legacy_engine.connect() as connection:
        assert await _ids(connection, "users") == [1, 2, 3]
        assert await _ids(connection, "subscriptions") == [1, 2, 3, 4]
        assert await _ids(connection, "transactions") == [1, 2, 3]
        assert await current_revision(connection) == "current"
        assert await _ids(connection, "legacy.users") == [1, 2, 3]
        assert await current_revision(connection, "legacy") == LEGACY_HEAD
        statuses = dict(
            (await connection.execute(text("SELECT id, status FROM subscriptions"))).all()
        )
        assert statuses == {1: "ACTIVE", 2: "DELETED", 3: "ACTIVE", 4: "ACTIVE"}
        language = await connection.scalar(text("SELECT language FROM users WHERE id = 2"))
        assert language == Locale.RU.name
        anchor = await connection.scalar(text("SELECT anchor_currency FROM pricing_settings"))
        assert anchor == "RUB"
        gateway = await connection.scalar(text("SELECT settings FROM payment_gateways"))
        assert gateway is not None and "secret" not in gateway
        assert await _ids(connection, "referrals") == [5]
        assert await connection.scalar(text("SELECT level FROM referrals")) == 1
        assert await _ids(connection, "referral_rewards") == [8]
        assert await _ids(connection, "promocodes") == [3]
        assert await _ids(connection, "promocode_activations") == [4]
        assert await _ids(connection, "oauth_identities") == [6]
        assert await _ids(connection, "ad_links") == [7]
        assert await connection.scalar(text("SELECT user_id FROM ad_link_attributions")) == 2
    assert result.report.counts["subscriptions"].migrated == 4


async def test_sequences_follow_max_id(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    await _run(legacy_engine, config)

    async with legacy_engine.begin() as connection:
        new_id = await connection.scalar(
            insert(User)
            .values(name="new", role=Role.USER, language=Locale.EN, is_blocked=False)
            .returning(User.id)
        )
    assert new_id == 4


async def test_failure_rolls_back_everything(
    legacy_engine: AsyncEngine,
    legacy_at: LegacyAt,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    original = migrate_module.transform_transactions

    def broken(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        rows = original(*args, **kwargs)
        rows[0]["user_id"] = 999
        return rows

    monkeypatch.setattr(migrate_module, "transform_transactions", broken)
    with pytest.raises(IntegrityError):
        await _run(legacy_engine, config)

    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == LEGACY_HEAD
        assert not await _legacy_schema_exists(connection)
        assert await _ids(connection, "users") == [1, 2, 3]


async def _claim_pending(connection: AsyncConnection) -> Optional[bool]:
    pending = await connection.scalar(text("SELECT owner_claim_pending FROM oauth_settings"))
    return cast(Optional[bool], pending)


def _bootstrap(session: AsyncSession, config: AppConfig) -> BootstrapOwnerUseCase:
    uow = UnitOfWork(session)
    return BootstrapOwnerUseCase(
        UserRepository(session),
        SettingsRepository(session),
        uow,
        config,
        OutboxEventPublisher(uow, RecordingDispatch()),
        SessionIssuer(SessionRepository(session), uow, config),
    )


async def _claim(engine: AsyncEngine, config: AppConfig, login: str) -> UserDto:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        owner, _ = await _bootstrap(session, config).execute(
            login=login, password=_OWNER_PASSWORD, client_ip="203.0.113.1", user_agent=None
        )
    return owner


async def test_owner_migrated_without_credentials_and_claim_pending(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    result = await _run(legacy_engine, config)

    assert result.owner_migrated
    async with legacy_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT role, login, password_hash, password_change_required "
                    "FROM users WHERE id = 1"
                )
            )
        ).one()
        assert await _claim_pending(connection) is True
    assert row.role == Role.OWNER.name
    assert row.login is None
    assert row.password_hash is None
    assert row.password_change_required is False


async def test_no_owner_leaves_no_claim(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    async with legacy_engine.begin() as connection:
        await _exec(connection, "UPDATE users SET role = 'USER' WHERE id = 1")
    result = await _run(legacy_engine, config)

    assert not result.owner_migrated
    async with legacy_engine.connect() as connection:
        assert not await _claim_pending(connection)


async def test_migrated_owner_claims_through_bootstrap(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    await _run(legacy_engine, config)

    owner = await _claim(legacy_engine, config, "boss")

    assert owner.id == 1
    assert owner.telegram_id == 1001
    assert owner.password_hash is not None
    assert await verify_password(_OWNER_PASSWORD, owner.password_hash, _crypt_key(config))
    async with legacy_engine.connect() as connection:
        assert await _claim_pending(connection) is False
        assert await connection.scalar(text("SELECT user_id FROM subscriptions WHERE id = 1")) == 1
    with pytest.raises(ConflictError) as exc_info:
        await _claim(legacy_engine, config, "intruder")
    assert exc_info.value.code is ErrorCode.OWNER_ALREADY_EXISTS


async def test_concurrent_claims_have_one_winner(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    await _run(legacy_engine, config)

    results = await asyncio.gather(
        _claim(legacy_engine, config, "first"),
        _claim(legacy_engine, config, "second"),
        return_exceptions=True,
    )

    winners = [r for r in results if isinstance(r, UserDto)]
    losers = [r for r in results if isinstance(r, ConflictError)]
    assert len(winners) == 1 and winners[0].id == 1
    assert len(losers) == 1 and losers[0].code is ErrorCode.OWNER_ALREADY_EXISTS
    async with legacy_engine.connect() as connection:
        login = await connection.scalar(text("SELECT login FROM users WHERE id = 1"))
    assert login == winners[0].login


async def test_migrate_refuses_schema_below_head(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await legacy_at(legacy_engine, "0039")
    with pytest.raises(LegacyMigrationError):
        await _run(legacy_engine, config)


async def test_preflight_rejects_unknown_revision(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    async with legacy_engine.begin() as connection:
        await _exec(connection, "UPDATE alembic_version SET version_num = '0047'")
    with pytest.raises(LegacyMigrationError, match="newer"):
        await preflight(legacy_engine, sdk=_panel(), crypt_key=_crypt_key(config))


async def test_preflight_treats_any_new_chain_revision_as_migrated(
    legacy_engine: AsyncEngine,
    legacy_at: LegacyAt,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    async with legacy_engine.begin() as connection:
        await _exec(connection, "UPDATE alembic_version SET version_num = '1a2b3c4d5e6f'")
    monkeypatch.setattr(
        migrate_module, "new_chain_revisions", lambda: frozenset({"current", "1a2b3c4d5e6f"})
    )
    with pytest.raises(LegacyMigrationError, match="already on the new schema"):
        await preflight(legacy_engine, sdk=_panel(), crypt_key=_crypt_key(config))


async def test_preflight_rejects_wrong_crypt_key(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    async with legacy_engine.begin() as connection:
        await _seed_gateway(connection, _enc("secret", Fernet.generate_key().decode()))
    with pytest.raises(LegacyMigrationError, match="APP_CRYPT_KEY"):
        await preflight(legacy_engine, sdk=_panel(), crypt_key=_crypt_key(config))


async def test_preflight_rejects_existing_legacy_schema(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    async with legacy_engine.begin() as connection:
        await _exec(connection, "CREATE SCHEMA legacy")
    with pytest.raises(LegacyMigrationError, match="legacy"):
        await preflight(legacy_engine, sdk=_panel(), crypt_key=_crypt_key(config))


async def test_preflight_rejects_old_panel(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    with pytest.raises(LegacyMigrationError, match="3.x"):
        await preflight(legacy_engine, sdk=_panel("2.7.0"), crypt_key=_crypt_key(config))


async def test_preflight_passes_on_a_legacy_database(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    await preflight(legacy_engine, sdk=_panel(), crypt_key=_crypt_key(config))


async def test_works_from_0039(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await legacy_at(legacy_engine, "0039")
    assert await upgrade_legacy_schema(legacy_engine) == "0039"
    async with legacy_engine.begin() as connection:
        await _seed_head(connection, _crypt_key(config))

    result = await migrate(
        legacy_engine,
        panel_index=_INDEX,
        crypt_key=_crypt_key(config),
        bot_owner_id=None,
        original_revision="0039",
    )

    assert result.original_revision == "0039"
    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == "current"
        assert await _ids(connection, "users") == [1, 2, 3]


async def test_subscription_price_comes_from_latest_completed_payment(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt, config: AppConfig
) -> None:
    await _prepare(legacy_engine, legacy_at, _crypt_key(config))
    async with legacy_engine.begin() as connection:
        await _exec(connection, "UPDATE transactions SET created_at = now() - interval '10 days'")
        rows = (
            # id, status, is_test, amount, currency, days ago
            (11, "COMPLETED", False, "77", "USD", 5),
            (12, "COMPLETED", False, "55", "RUB", 8),
            (13, "PENDING", False, "999", "RUB", 1),
            (14, "COMPLETED", True, "1", "XTR", 1),
        )
        for tx_id, status, is_test, amount, currency, days in rows:
            pricing = json.dumps(
                {"original_amount": amount, "final_amount": amount, "discount_percent": 0}
            )
            await _exec(
                connection,
                "INSERT INTO transactions (id, payment_id, status, is_test, purchase_type, "
                "gateway_type, pricing, currency, plan_snapshot, user_id, created_at) VALUES "
                "(:id, gen_random_uuid(), CAST(:status AS transaction_status), :is_test, 'NEW', "
                "'YOOKASSA', CAST(:pricing AS jsonb), CAST(:currency AS currency), "
                "CAST(:snapshot AS jsonb), 3, now() - make_interval(days => :days))",
                id=tx_id,
                status=status,
                is_test=is_test,
                pricing=pricing,
                currency=currency,
                snapshot=json.dumps(_SNAPSHOT),
                days=days,
            )
    await _run(legacy_engine, config)

    async with legacy_engine.connect() as connection:
        snapshot = await connection.scalar(
            text("SELECT plan_snapshot FROM subscriptions WHERE id = 4")
        )
    assert (snapshot["price_paid"], snapshot["currency"]) == ("77", "USD")
