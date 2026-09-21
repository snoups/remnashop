import re
from enum import Enum
from pathlib import Path
from typing import Final

from remnapy.enums import TrafficLimitStrategy

from app.core.enums import (
    AddOnType,
    AdLinkChannel,
    BackupKind,
    BackupRunStatus,
    Currency,
    DiscountSource,
    Locale,
    OAuthProvider,
    PaymentGatewayType,
    PaymentOrderStatus,
    PlanAvailability,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralRewardType,
    Role,
    SubscriptionStatus,
)
from app.core.events import EventCategory

_MIGRATION: Final[Path] = (
    Path(__file__).parents[3]
    / "app"
    / "core"
    / "db"
    / "migrations"
    / "versions"
    / "current_current.py"
)

# Every native Postgres ENUM type the committed migration declares, mapped to
# the Python enum it must stay in sync with. A persisted enum missing from
# this map fails test_every_migration_enum_is_mapped -- add the entry.
_ENUM_BY_PG_NAME: Final[dict[str, type[Enum]]] = {
    "addontype": AddOnType,
    "adlinkchannel": AdLinkChannel,
    "backupkind": BackupKind,
    "backuprunstatus": BackupRunStatus,
    "currency": Currency,
    "discountsource": DiscountSource,
    "event_category": EventCategory,
    "locale": Locale,
    "oauth_provider": OAuthProvider,
    "payment_gateway_type": PaymentGatewayType,
    "paymentorderstatus": PaymentOrderStatus,
    "planavailability": PlanAvailability,
    "plantype": PlanType,
    "promocodeavailability": PromocodeAvailability,
    "promocoderewardtype": PromocodeRewardType,
    "purchasetype": PurchaseType,
    "referralaccrualstrategy": ReferralAccrualStrategy,
    "referralrewardtype": ReferralRewardType,
    "subscriptionstatus": SubscriptionStatus,
    "trafficlimitstrategy": TrafficLimitStrategy,
    "user_role": Role,
}

_SA_ENUM_RE: Final[re.Pattern[str]] = re.compile(
    r"sa\.Enum\(\s*((?:\"[A-Z_]+\",?\s*)+)name=\"([a-z_]+)\"", re.MULTILINE
)


def _migration_enums() -> dict[str, set[str]]:
    text = _MIGRATION.read_text()
    result: dict[str, set[str]] = {}
    for values_blob, pg_name in _SA_ENUM_RE.findall(text):
        result[pg_name] = set(re.findall(r"\"([A-Z_]+)\"", values_blob))
    return result


def test_migration_file_has_enum_declarations() -> None:
    # Guards the regex itself -- if current_current.py's formatting changes
    # such that nothing matches, every other assertion here would vacuously
    # pass.
    assert len(_migration_enums()) >= 10


def test_every_migration_enum_is_mapped() -> None:
    unmapped = set(_migration_enums()) - set(_ENUM_BY_PG_NAME)
    assert not unmapped, (
        f"persisted enum(s) {sorted(unmapped)} are in the migration but not in "
        f"_ENUM_BY_PG_NAME -- add the mapping so drift on them is checked too"
    )


def test_every_mapped_enum_is_still_in_the_migration() -> None:
    missing = set(_ENUM_BY_PG_NAME) - set(_migration_enums())
    assert not missing, (
        f"_ENUM_BY_PG_NAME maps {sorted(missing)} but the migration no longer "
        f"declares them -- the mapping is stale, or the migration is"
    )


def test_python_enums_match_the_migration() -> None:
    migration = _migration_enums()
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
        f"enum drift between Python and current_current.py: {drift}. "
        f"Run `cd backend && uv run alembic revision --autogenerate -m current` "
        f"and commit the regenerated migration."
    )
