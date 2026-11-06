from enum import Enum
from typing import Final

from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    AccessMode,
    AddOnType,
    AdLinkChannel,
    BackupKind,
    BackupRunStatus,
    BroadcastCategory,
    BroadcastChannel,
    BroadcastDelivery,
    BroadcastMediaType,
    BroadcastRecipientStatus,
    BroadcastStatus,
    CaptchaProvider,
    Currency,
    DiscountSource,
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    OAuthProvider,
    PaymentGatewayType,
    PlanAvailability,
    PlanBadge,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseChannel,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
    RegistrationSource,
    Role,
    RoundingMode,
    SessionAudience,
    SmtpSecurity,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.events import EventCategory

# Every native Postgres ENUM type the migrations create, mapped to
# the Python enum it must stay in sync with. A persisted enum missing from
# this map fails test_every_migration_enum_is_mapped.
_ENUM_BY_PG_NAME: Final[dict[str, type[Enum]]] = {
    "accessmode": AccessMode,
    "addontype": AddOnType,
    "adlinkchannel": AdLinkChannel,
    "registrationsource": RegistrationSource,
    "backupkind": BackupKind,
    "backuprunstatus": BackupRunStatus,
    "broadcastcategory": BroadcastCategory,
    "captchaprovider": CaptchaProvider,
    "broadcastchannel": BroadcastChannel,
    "broadcastdelivery": BroadcastDelivery,
    "broadcastmediatype": BroadcastMediaType,
    "broadcastrecipientstatus": BroadcastRecipientStatus,
    "broadcaststatus": BroadcastStatus,
    "currency": Currency,
    "discountsource": DiscountSource,
    "event_category": EventCategory,
    "legalacceptancetrigger": LegalAcceptanceTrigger,
    "legaldocumentkind": LegalDocumentKind,
    "locale": Locale,
    "oauth_provider": OAuthProvider,
    "payment_gateway_type": PaymentGatewayType,
    "sessionaudience": SessionAudience,
    "transactionstatus": TransactionStatus,
    "planavailability": PlanAvailability,
    "planbadge": PlanBadge,
    "plantype": PlanType,
    "promocodeavailability": PromocodeAvailability,
    "promocoderewardtype": PromocodeRewardType,
    "purchasechannel": PurchaseChannel,
    "purchasetype": PurchaseType,
    "referralaccrualstrategy": ReferralAccrualStrategy,
    "referralrewardtype": ReferralRewardType,
    "referralrewardstrategy": ReferralRewardStrategy,
    "roundingmode": RoundingMode,
    "smtpsecurity": SmtpSecurity,
    "subscriptionstatus": SubscriptionStatus,
    "trafficlimitstrategy": TrafficLimitStrategy,
    "user_role": Role,
}

# the test database is built by `alembic upgrade head`, so its enums are what the
# whole chain produces, later `ALTER TYPE ... ADD VALUE` revisions included
_ENUM_LABELS_SQL: Final[str] = """
    SELECT t.typname, e.enumlabel
    FROM pg_type t
    JOIN pg_enum e ON e.enumtypid = t.oid
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public'
"""


async def _migration_enums(session: AsyncSession) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for pg_name, label in (await session.execute(text(_ENUM_LABELS_SQL))).all():
        result.setdefault(pg_name, set()).add(label)
    return result


async def test_migrations_create_enums(session: AsyncSession) -> None:
    # an empty result would make every other assertion here pass vacuously
    assert len(await _migration_enums(session)) >= 10


async def test_every_migration_enum_is_mapped(session: AsyncSession) -> None:
    unmapped = set(await _migration_enums(session)) - set(_ENUM_BY_PG_NAME)
    assert not unmapped, (
        f"persisted enum(s) {sorted(unmapped)} are in the migration but not in "
        f"_ENUM_BY_PG_NAME -- add the mapping so drift on them is checked too"
    )


async def test_every_mapped_enum_is_still_in_the_migration(session: AsyncSession) -> None:
    missing = set(_ENUM_BY_PG_NAME) - set(await _migration_enums(session))
    assert not missing, (
        f"_ENUM_BY_PG_NAME maps {sorted(missing)} but the migration no longer "
        f"declares them -- the mapping is stale, or the migration is"
    )


async def test_python_enums_match_the_migration(session: AsyncSession) -> None:
    migration = await _migration_enums(session)
    drift: dict[str, dict[str, list[str]]] = {}
    for pg_name, enum_cls in _ENUM_BY_PG_NAME.items():
        if pg_name not in migration:
            continue
        # SQLAlchemy's native Enum type generates Postgres labels from .name, not .value.
        # See Role (IntEnum) or BannerFormat (plain StrEnum) where they diverge.
        python_names = {member.name for member in enum_cls}
        if python_names != migration[pg_name]:
            drift[pg_name] = {
                "python_only": sorted(python_names - migration[pg_name]),
                "migration_only": sorted(migration[pg_name] - python_names),
            }
    assert not drift, (
        f"enum drift between Python and the migrations: {drift}. Add a revision "
        f"(`uv run alembic revision -m ...`) with `ALTER TYPE ... ADD VALUE` for new "
        f"labels -- autogenerate doesn't detect them."
    )
