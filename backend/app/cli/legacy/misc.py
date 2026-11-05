from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final, Optional

from app.cli.legacy.report import MigrationReport
from app.core.enums import AdLinkChannel, Currency, OAuthProvider

_OAUTH_PROVIDERS: Final[frozenset[OAuthProvider]] = frozenset(
    {OAuthProvider.GOOGLE, OAuthProvider.YANDEX}
)
_COPIED: Final[tuple[str, ...]] = ("id", "name", "code", "is_active", "created_at", "updated_at")


def transform_ad_links(
    rows: Sequence[Mapping[str, Any]], *, anchor_currency: Currency
) -> list[dict[str, Any]]:
    return [
        {
            **{column: row[column] for column in _COPIED},
            "cost": Decimal(0),
            "cost_currency": anchor_currency,
            "allow_bot": True,
            "allow_webcabinet": True,
        }
        for row in sorted(rows, key=lambda r: int(r["id"]))
    ]


def ad_link_attributions(users: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ad_link_id": user["ad_link_id"],
            "user_id": user["id"],
            "channel": AdLinkChannel.BOT,
            "created_at": user["created_at"],
        }
        for user in sorted(users, key=lambda u: int(u["id"]))
        if user["ad_link_id"] is not None
    ]


def transform_oauth(
    rows: Sequence[Mapping[str, Any]], report: MigrationReport
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: int(r["id"])):
        provider: Optional[OAuthProvider]
        try:
            provider = OAuthProvider(str(row["provider"]).upper())
        except ValueError:
            provider = None
        if provider not in _OAUTH_PROVIDERS:
            report.skip("user_oauth_providers", str(row["id"]), f"unsupported {row['provider']}")
            continue
        result.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "provider": provider,
                "external_id": row["provider_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    report.count("user_oauth_providers", len(rows), len(result))
    return result
