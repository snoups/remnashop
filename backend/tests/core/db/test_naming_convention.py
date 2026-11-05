from typing import Final

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint

from app.core.db import models  # noqa: F401 (registers models on BaseSql.metadata)
from app.core.db.base import BaseSql

_POSTGRES_NAME_LIMIT: Final[int] = 63

_CHECK_NAMES: Final[frozenset[str]] = frozenset(
    {
        "ck_addons_base_price_positive",
        "ck_currency_rates_charm_ending_range",
        "ck_currency_rates_min_amount_nonneg",
        "ck_currency_rates_rate_positive",
        "ck_plan_durations_base_price_non_negative",
        "ck_plans_discount_percent_range",
        "ck_referrals_level_range",
        "ck_users_bonus_days_non_negative",
        "ck_users_email_lowercase",
        "ck_users_login_charset",
        "ck_users_loyalty_discount_range",
        "ck_users_personal_discount_range",
        "ck_users_points_non_negative",
        "ck_users_purchase_discount_range",
    }
)

# names the repositories compare against the constraint of an IntegrityError
_COMPARED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "ux_oauth_identities_provider_external_id",
        "ix_addons_name",
        "fk_promocodes_reward_addon_id_addons",
        "fk_promocodes_reward_plan_id_plans",
        "ix_plans_public_code",
        "ix_plans_name",
        "uq_referrals_referred_id",
        "uq_referral_rewards_payment_referral",
        "ix_promocodes_code",
        "ux_blacklist_sources_url",
        "ux_users_single_owner",
        "ix_users_login",
        "ix_users_telegram_id",
        "ix_users_email_canonical",
        "ix_ad_links_code",
        "ux_ad_link_attributions_user_id",
        "ux_active_locales_locale",
    }
)


def _names(kind: type) -> set[str]:
    return {
        str(c.name)
        for table in BaseSql.metadata.tables.values()
        for c in table.constraints
        if isinstance(c, kind) and c.name is not None
    }


def _all_names() -> set[str]:
    names = _names(CheckConstraint) | _names(UniqueConstraint)
    for table in BaseSql.metadata.tables.values():
        names |= {str(i.name) for i in table.indexes}
    return names


def test_check_constraint_names_unchanged() -> None:
    assert _names(CheckConstraint) == _CHECK_NAMES


def test_compared_constraint_names_exist() -> None:
    names = _all_names() | _names(ForeignKeyConstraint)
    assert _COMPARED_NAMES <= names


def test_every_constraint_named() -> None:
    for table in BaseSql.metadata.tables.values():
        for c in table.constraints:
            if isinstance(c, (PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint)):
                assert c.name is not None, f"{table.name}: unnamed {type(c).__name__}"
                assert len(str(c.name)) <= _POSTGRES_NAME_LIMIT, c.name
