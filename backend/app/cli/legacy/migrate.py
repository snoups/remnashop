from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Optional, TypeVar

from alembic import command
from alembic.config import Config
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from sqlalchemy import Connection, insert, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.gateways import decrypt_legacy, transform_gateways
from app.cli.legacy.misc import ad_link_attributions, transform_ad_links, transform_oauth
from app.cli.legacy.panel import PanelIndex, assert_panel_v3
from app.cli.legacy.plans import transform_plans
from app.cli.legacy.promocodes import transform_promocodes
from app.cli.legacy.referrals import transform_referrals
from app.cli.legacy.report import MigrationReport
from app.cli.legacy.schema import (
    LEGACY_HEAD,
    LEGACY_REVISIONS,
    current_revision,
    new_chain_revisions,
    record_origin,
    recorded_origin,
    upgrade_legacy,
)
from app.cli.legacy.settings import transform_settings
from app.cli.legacy.subscriptions import migrated_subscription_ids, transform_subscriptions
from app.cli.legacy.transactions import transform_transactions
from app.cli.legacy.users import transform_users
from app.core.db.base import BaseSql
from app.core.db.models import (
    AccessSettings,
    AdLink,
    AdLinkAttribution,
    BotRequirements,
    OAuthIdentity,
    OAuthSettings,
    PaymentGateway,
    Plan,
    PlanDuration,
    PlanPriceOverride,
    PricingSettings,
    Promocode,
    PromocodeActivation,
    Referral,
    ReferralReward,
    ReferralSettings,
    Subscription,
    Transaction,
    User,
)
from app.core.db.singleton import SINGLETON_ID
from app.core.enums import Currency, Locale, ReferralLevel, Role, SubscriptionStatus

_NEW_MIGRATIONS_DIR: Final[Path] = Path(__file__).parents[2] / "core" / "db" / "migrations"
_DEFAULT_LOCALE: Final[Locale] = Locale.EN
_DEFAULT_ANCHOR: Final[Currency] = Currency.USD
_ENCRYPTED_PREFIX: Final[str] = "enc_"
_COMPLETED: Final[str] = "COMPLETED"

_Row = TypeVar("_Row", bound=Mapping[str, Any])


@dataclass(frozen=True, kw_only=True)
class MigrationResult:
    report: MigrationReport
    owner_migrated: bool
    original_revision: str


async def flush_shop_redis(redis: Redis) -> None:
    # the old broker keeps `taskiq` as a stream, the new one reads it as a list
    await redis.flushdb()


async def _legacy_schema_exists(connection: AsyncConnection) -> bool:
    found = await connection.scalar(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'legacy'")
    )
    return found is not None


def _check_revision(revision: Optional[str]) -> None:
    if revision is None:
        raise LegacyMigrationError("No old-version database found: alembic_version is missing")
    if revision in new_chain_revisions():
        raise LegacyMigrationError("The database is already on the new schema")
    if revision not in LEGACY_REVISIONS:
        raise LegacyMigrationError(
            f"Database revision {revision} is newer than supported ({LEGACY_HEAD})"
        )


async def _first_encrypted_secret(connection: AsyncConnection) -> Optional[str]:
    rows = await connection.scalars(
        text("SELECT settings FROM payment_gateways WHERE settings IS NOT NULL ORDER BY id")
    )
    for settings in rows:
        for value in settings.values():
            if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
                return value
    return None


async def preflight(engine: AsyncEngine, *, sdk: RemnawaveSDK, crypt_key: str) -> None:
    async with engine.connect() as connection:
        _check_revision(await current_revision(connection))
        if await _legacy_schema_exists(connection):
            raise LegacyMigrationError(
                "Schema 'legacy' already exists: a previous migration is still kept"
            )
        secret = await _first_encrypted_secret(connection)
    if secret is not None:
        try:
            decrypt_legacy(secret, crypt_key)
        except Exception as error:
            raise LegacyMigrationError(
                "APP_CRYPT_KEY does not match the old one: set the key the old version used"
            ) from error
    await assert_panel_v3(sdk)


async def legacy_origin(connection: AsyncConnection) -> Optional[str]:
    """The revision the old image ran on: recorded by an earlier upgrade, else the current one."""
    return await recorded_origin(connection, "public") or await current_revision(connection)


async def upgrade_legacy_schema(engine: AsyncEngine) -> str:
    """Brings public up to LEGACY_HEAD, a commit per migration; returns the original revision."""
    async with engine.connect() as connection:
        _check_revision(await current_revision(connection))
        original = await legacy_origin(connection)
        assert original is not None
        await record_origin(connection, "public", original)
        await connection.commit()
        await connection.run_sync(upgrade_legacy)
    return original


def _create_new_schema(connection: Connection) -> None:
    config = Config()
    config.set_main_option("script_location", str(_NEW_MIGRATIONS_DIR))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def _read(connection: AsyncConnection, table: str) -> list[dict[str, Any]]:
    result = await connection.execute(text(f"SELECT * FROM legacy.{table} ORDER BY id"))
    return [dict(row) for row in result.mappings()]


async def _insert(
    connection: AsyncConnection, model: type[BaseSql], rows: Sequence[Mapping[str, Any]]
) -> None:
    # executemany binds the first row's keys: one batch per key set, defaults stay intact
    batches: dict[frozenset[str], list[Mapping[str, Any]]] = {}
    for row in rows:
        batches.setdefault(frozenset(row), []).append(row)
    for batch in batches.values():
        await connection.execute(insert(model), batch)


async def _set_sequences(connection: AsyncConnection, tables: Iterable[str]) -> None:
    for table in tables:
        await connection.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), max(id)) FROM {table} "
                "HAVING max(id) IS NOT NULL"
            )
        )


def _used_currencies(
    gateways: Sequence[Mapping[str, Any]], transactions: Sequence[Mapping[str, Any]]
) -> frozenset[Currency]:
    """What the old shop took payment in: an active gateway's currency, or a completed payment's."""
    active = {Currency(row["currency"]) for row in gateways if row["is_active"]}
    paid = {
        Currency(row["currency"])
        for row in transactions
        if str(row["status"]) == _COMPLETED and not row["is_test"]
    }
    return frozenset(active | paid)


def _last_payments(
    transactions: Sequence[Mapping[str, Any]],
) -> dict[tuple[int, int], tuple[Decimal, Currency]]:
    result: dict[tuple[int, int], tuple[Decimal, Currency]] = {}
    completed = (
        row for row in transactions if str(row["status"]) == _COMPLETED and not row["is_test"]
    )
    for row in sorted(completed, key=lambda r: (r["created_at"], int(r["id"]))):
        key = (int(row["user_id"]), int(row["plan_snapshot"]["id"]))
        result[key] = (Decimal(str(row["pricing"]["final_amount"])), Currency(row["currency"]))
    return result


def _owned(
    rows: Sequence[_Row], user_ids: set[int], table: str, report: MigrationReport
) -> list[_Row]:
    kept = [row for row in rows if int(row["user_id"]) in user_ids]
    for row in rows:
        if int(row["user_id"]) not in user_ids:
            report.skip(table, str(row["id"]), f"user {row['user_id']} not migrated")
    return kept


def _set_locales(users: list[dict[str, Any]], report: MigrationReport) -> None:
    for user in users:
        name = str(user["language"])
        if name in Locale.__members__:
            user["language"] = Locale[name]
        else:
            user["language"] = _DEFAULT_LOCALE
            report.notes.append(
                f"users #{user['id']}: language {name} unsupported, set to {_DEFAULT_LOCALE.name}"
            )


async def migrate(
    engine: AsyncEngine,
    *,
    panel_index: PanelIndex,
    crypt_key: str,
    bot_owner_id: Optional[int],
    original_revision: str,
) -> MigrationResult:
    report = MigrationReport()
    if original_revision != LEGACY_HEAD:
        report.notes.append(f"Old schema upgraded from {original_revision} to {LEGACY_HEAD}")

    async with engine.begin() as connection:
        revision = await current_revision(connection)
        if revision != LEGACY_HEAD or await _legacy_schema_exists(connection):
            raise LegacyMigrationError(
                f"Expected an old-version database at {LEGACY_HEAD}, found {revision}"
            )
        await connection.execute(text("ALTER SCHEMA public RENAME TO legacy"))
        await record_origin(connection, "legacy", original_revision)
        await connection.execute(text("CREATE SCHEMA public"))
        await connection.run_sync(_create_new_schema)

        owner_migrated = await _transfer(
            connection,
            panel_index=panel_index,
            crypt_key=crypt_key,
            bot_owner_id=bot_owner_id,
            report=report,
        )

    return MigrationResult(
        report=report, owner_migrated=owner_migrated, original_revision=original_revision
    )


async def _transfer(
    connection: AsyncConnection,
    *,
    panel_index: PanelIndex,
    crypt_key: str,
    bot_owner_id: Optional[int],
    report: MigrationReport,
) -> bool:
    settings_rows = await _read(connection, "settings")
    settings = transform_settings(settings_rows[0], report) if settings_rows else None
    if settings is None:
        report.notes.append("settings: no old settings row, defaults kept")
    anchor = settings.anchor_currency if settings else _DEFAULT_ANCHOR

    legacy_gateways = await _read(connection, "payment_gateways")
    legacy_transactions = await _read(connection, "transactions")
    legacy_plans = await _read(connection, "plans")
    plans = transform_plans(
        legacy_plans,
        await _read(connection, "plan_durations"),
        await _read(connection, "plan_prices"),
        anchor_currency=anchor,
        used_currencies=_used_currencies(legacy_gateways, legacy_transactions),
        report=report,
    )
    plan_ids = {int(plan["id"]) for plan in plans.plans}
    plan_codes = {int(plan["id"]): str(plan["public_code"]) for plan in legacy_plans}

    legacy_users = await _read(connection, "users")
    subscriptions = transform_subscriptions(
        await _read(connection, "subscriptions"),
        users={int(user["id"]): user for user in legacy_users},
        current_subscription_ids={
            int(user["current_subscription_id"])
            for user in legacy_users
            if user["current_subscription_id"] is not None
        },
        index=panel_index,
        plan_codes=plan_codes,
        last_payments=_last_payments(legacy_transactions),
        anchor_currency=anchor,
        report=report,
    )
    users = transform_users(
        legacy_users,
        bot_owner_id=bot_owner_id,
        live_subscription_user_ids={
            int(sub["user_id"])
            for sub in subscriptions
            if sub["status"] is not SubscriptionStatus.DELETED
        },
        report=report,
    )
    report.count("users", len(legacy_users), len(users))
    _set_locales(users, report)
    owner_migrated = any(user["role"] is Role.OWNER for user in users)
    user_ids = {int(user["id"]) for user in users}

    source_subscriptions = report.counts["subscriptions"].source
    subscriptions = _owned(subscriptions, user_ids, "subscriptions", report)
    report.count("subscriptions", source_subscriptions, len(subscriptions))
    subscription_ids = migrated_subscription_ids(subscriptions)

    transactions = transform_transactions(
        _owned(legacy_transactions, user_ids, "transactions", report),
        plan_ids=plan_ids,
        subscription_ids=subscription_ids,
        # an account without Telegram could only buy through the old web cabinet
        cabinet_user_ids={int(user["id"]) for user in users if user["telegram_id"] is None},
        anchor_currency=anchor,
        rates={},
        report=report,
        plan_codes=plan_codes,
    )
    report.count("transactions", len(legacy_transactions), len(transactions))

    legacy_ad_links = await _read(connection, "ad_links")
    ad_links = transform_ad_links(legacy_ad_links, anchor_currency=anchor)
    report.count("ad_links", len(legacy_ad_links), len(ad_links))
    ad_link_ids = {int(link["id"]) for link in ad_links}
    attributions = ad_link_attributions(
        [
            user
            for user in legacy_users
            if int(user["id"]) in user_ids and user["ad_link_id"] in ad_link_ids
        ]
    )
    report.count(
        "ad_link_attributions",
        sum(user["ad_link_id"] is not None for user in legacy_users),
        len(attributions),
    )

    legacy_oauth = await _read(connection, "user_oauth_providers")
    oauth = transform_oauth(_owned(legacy_oauth, user_ids, "user_oauth_providers", report), report)
    report.count("user_oauth_providers", len(legacy_oauth), len(oauth))

    promocodes, activations = transform_promocodes(
        await _read(connection, "promocodes"),
        await _read(connection, "promocode_activations"),
        plan_ids=plan_ids,
        user_ids=user_ids,
        report=report,
    )
    referrals, rewards = transform_referrals(
        [
            {**row, "level": ReferralLevel[str(row["level"])]}
            for row in await _read(connection, "referrals")
        ],
        await _read(connection, "referral_rewards"),
        user_ids=user_ids,
        subscription_ids=subscription_ids,
        report=report,
    )
    gateways = transform_gateways(legacy_gateways, crypt_key=crypt_key, report=report)

    batches: list[tuple[type[BaseSql], Sequence[Mapping[str, Any]]]] = [
        (Plan, plans.plans),
        (PlanDuration, plans.durations),
        (PlanPriceOverride, plans.overrides),
        (AdLink, ad_links),
        (User, users),
        (AdLinkAttribution, attributions),
        (OAuthIdentity, oauth),
        (Subscription, subscriptions),
        (Transaction, transactions),
        (Promocode, promocodes),
        (PromocodeActivation, activations),
        (Referral, referrals),
        (ReferralReward, rewards),
        (PaymentGateway, gateways),
    ]
    if settings is not None:
        batches += [
            (AccessSettings, [settings.access]),
            (BotRequirements, [settings.bot_requirements]),
            (ReferralSettings, [settings.referral]),
            (PricingSettings, [{"id": SINGLETON_ID, "anchor_currency": anchor}]),
        ]
    if owner_migrated:
        # the owner sets a login and password through the dashboard's bootstrap
        batches.append((OAuthSettings, [{"id": SINGLETON_ID, "owner_claim_pending": True}]))
    for model, rows in batches:
        await _insert(connection, model, rows)
    await _set_sequences(
        connection, (model.__tablename__ for model, rows in batches if rows and "id" in rows[0])
    )
    return owner_migrated
