from app.core.enums import PriceAdjustScope, Role, RoundingMode
from app.core.security.permissions import (
    GRANTABLE_PERMISSIONS,
    PERMISSION_METADATA,
    ROLE_PERMISSIONS,
    Permission,
)


def test_rounding_mode_values() -> None:
    assert RoundingMode.INTEGER.value == "INTEGER"
    assert RoundingMode.DECIMAL_2.value == "DECIMAL_2"


def test_price_adjust_scope_values() -> None:
    assert {s.value for s in PriceAdjustScope} == {"ALL_PLANS", "ALL_ADDONS", "SELECTED"}


def test_pricing_view_is_grantable_and_admin_has_it() -> None:
    assert Permission.PRICING_VIEW in PERMISSION_METADATA
    assert Permission.PRICING_VIEW in GRANTABLE_PERMISSIONS
    assert Permission.PRICING_VIEW in ROLE_PERMISSIONS[Role.ADMIN]


def test_pricing_rates_manage_is_owner_only_and_not_grantable() -> None:
    assert Permission.PRICING_RATES_MANAGE not in PERMISSION_METADATA
    assert Permission.PRICING_RATES_MANAGE not in GRANTABLE_PERMISSIONS
    assert Permission.PRICING_RATES_MANAGE not in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.PRICING_RATES_MANAGE in ROLE_PERMISSIONS[Role.OWNER]
