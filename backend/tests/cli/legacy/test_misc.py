from datetime import datetime, timezone
from decimal import Decimal

from app.cli.legacy.misc import ad_link_attributions, transform_ad_links, transform_oauth
from app.cli.legacy.report import MigrationReport
from app.core.enums import AdLinkChannel, Currency, OAuthProvider

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_ad_link_zero_cost_both_channels() -> None:
    row = {
        "id": 1,
        "name": "x",
        "code": "c",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    (link,) = transform_ad_links([row], anchor_currency=Currency.RUB)
    assert link["cost"] == Decimal(0)
    assert link["cost_currency"] is Currency.RUB
    assert link["allow_bot"] is True
    assert link["allow_webcabinet"] is True
    assert link["code"] == "c"


def test_attribution_from_users_ad_link_id() -> None:
    users = [
        {"id": 1, "ad_link_id": 7, "created_at": NOW},
        {"id": 2, "ad_link_id": None, "created_at": NOW},
    ]
    assert ad_link_attributions(users) == [
        {"ad_link_id": 7, "user_id": 1, "channel": AdLinkChannel.BOT, "created_at": NOW}
    ]


def _oauth(provider: str, row_id: int = 1) -> dict[str, object]:
    return {
        "id": row_id,
        "user_id": 3,
        "provider": provider,
        "provider_id": "abc",
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_oauth_vk_skipped() -> None:
    report = MigrationReport()
    assert transform_oauth([_oauth("vk")], report) == []
    assert report.skips[0].table == "user_oauth_providers"


def test_oauth_provider_uppercased() -> None:
    (row,) = transform_oauth([_oauth("google")], MigrationReport())
    assert row["provider"] is OAuthProvider.GOOGLE
    assert row["external_id"] == "abc"
    assert row["user_id"] == 3
