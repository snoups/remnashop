from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest

from app.core.exceptions import ValidationError
from app.modules.loyalty.dto import LoyaltyTierDto
from app.modules.loyalty.tiers import months_before, next_tier, resolve_percent, validate_tiers

TIERS = [
    LoyaltyTierDto(threshold=Decimal("1000"), percent=3),
    LoyaltyTierDto(threshold=Decimal("5000"), percent=7),
]


def test_resolve_percent_includes_the_threshold() -> None:
    assert resolve_percent(Decimal("1000"), TIERS) == 3
    assert resolve_percent(Decimal("999.99"), TIERS) == 0
    assert resolve_percent(Decimal("9000"), TIERS) == 7
    assert resolve_percent(Decimal("9000"), []) == 0


def test_next_tier() -> None:
    assert next_tier(Decimal("0"), TIERS) == TIERS[0]
    assert next_tier(Decimal("1000"), TIERS) == TIERS[1]
    assert next_tier(Decimal("5000"), TIERS) is None


def test_months_before_clamps_the_day() -> None:
    moment = datetime(2026, 3, 31, 12, tzinfo=timezone.utc)
    assert months_before(moment, 1) == datetime(2026, 2, 28, 12, tzinfo=timezone.utc)
    assert months_before(moment, 15) == datetime(2024, 12, 31, 12, tzinfo=timezone.utc)
    assert months_before(datetime(2024, 3, 31, tzinfo=timezone.utc), 1).day == 29


@pytest.mark.parametrize(
    ("tiers", "window"),
    [
        (
            [
                LoyaltyTierDto(threshold=Decimal("100"), percent=5),
                LoyaltyTierDto(threshold=Decimal("100"), percent=7),
            ],
            None,
        ),
        (
            [
                LoyaltyTierDto(threshold=Decimal("100"), percent=7),
                LoyaltyTierDto(threshold=Decimal("200"), percent=7),
            ],
            None,
        ),
        ([LoyaltyTierDto(threshold=Decimal("100"), percent=0)], None),
        ([LoyaltyTierDto(threshold=Decimal("100"), percent=101)], None),
        ([LoyaltyTierDto(threshold=Decimal("0"), percent=5)], None),
        ([LoyaltyTierDto(threshold=Decimal("100"), percent=5)], 0),
    ],
)
def test_validate_tiers_rejects(tiers: list[LoyaltyTierDto], window: Optional[int]) -> None:
    with pytest.raises(ValidationError):
        validate_tiers(tiers, window)


def test_validate_tiers_accepts_increasing_tiers() -> None:
    validate_tiers(TIERS, 12)
    validate_tiers([], None)
