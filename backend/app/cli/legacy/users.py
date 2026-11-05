from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final, Optional

from app.cli.legacy.report import MigrationReport
from app.core.enums import Role
from app.core.utils.email import canonical_email
from app.modules.users import generate_referral_code

_TABLE: Final[str] = "users"
_REFERRAL_CODE_MAX_LENGTH: Final[int] = 16
_LEGACY_ROLES: Final[dict[str, Role]] = {
    "USER": Role.USER,
    "PREVIEW": Role.USER,
    "ADMIN": Role.ADMIN,
    "DEV": Role.ADMIN,
    "OWNER": Role.ADMIN,
}
_COPIED: Final[tuple[str, ...]] = (
    "id",
    "telegram_id",
    "username",
    "name",
    "language",
    "personal_discount",
    "purchase_discount",
    "is_blocked",
    "is_bot_blocked",
    "is_trial_available",
    "referral_code_reset_at",
    "created_at",
    "updated_at",
)


def pick_owner_id(rows: Sequence[Mapping[str, Any]], bot_owner_id: Optional[int]) -> Optional[int]:
    if bot_owner_id is not None:
        for row in rows:
            if row["telegram_id"] == bot_owner_id:
                return int(row["id"])
    owners = [int(row["id"]) for row in rows if str(row["role"]) == "OWNER"]
    return min(owners) if owners else None


def _email_holders(
    rows: Sequence[Mapping[str, Any]], live_subscription_user_ids: set[int]
) -> dict[int, str]:
    # one holder per canonical address: a live subscription wins, then the lowest id
    best: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not row.get("email"):
            continue
        key = canonical_email(row["email"])
        current = best.get(key)
        if current is None or _email_rank(row, live_subscription_user_ids) < _email_rank(
            current, live_subscription_user_ids
        ):
            best[key] = row
    return {int(row["id"]): key for key, row in best.items()}


def _email_rank(row: Mapping[str, Any], live: set[int]) -> tuple[bool, int]:
    return (int(row["id"]) not in live, int(row["id"]))


def transform_users(
    rows: Sequence[Mapping[str, Any]],
    *,
    bot_owner_id: Optional[int],
    live_subscription_user_ids: set[int],
    report: MigrationReport,
) -> list[dict[str, Any]]:
    owner_id = pick_owner_id(rows, bot_owner_id)
    if owner_id is None:
        report.notes.append("No owner in the legacy data: create one via POST /auth/bootstrap")
    email_holders = _email_holders(rows, live_subscription_user_ids)
    taken_codes = {
        row["referral_code"]
        for row in rows
        if row.get("referral_code") and len(row["referral_code"]) <= _REFERRAL_CODE_MAX_LENGTH
    }

    result: list[dict[str, Any]] = []
    for row in rows:
        user_id = int(row["id"])
        legacy_role = str(row["role"])
        if legacy_role not in _LEGACY_ROLES:
            report.skip(_TABLE, str(user_id), f"unsupported legacy role {legacy_role}")
            continue
        role = Role.OWNER if user_id == owner_id else _LEGACY_ROLES[legacy_role]

        email: Optional[str] = None
        if row.get("email"):
            if email_holders.get(user_id) is not None:
                email = row["email"].strip().lower()
            else:
                report.skip(_TABLE, str(user_id), "email dropped: same mailbox as another user")

        code = row.get("referral_code")
        if code and len(code) > _REFERRAL_CODE_MAX_LENGTH:
            while True:
                new_code = generate_referral_code()
                if new_code not in taken_codes:
                    break
            taken_codes.add(new_code)
            report.notes.append(f"users #{user_id}: referral code longer than 16 regenerated")
            code = new_code

        item = {column: row.get(column) for column in _COPIED}
        item.update(
            role=role,
            email=email,
            email_canonical=canonical_email(email) if email else None,
            password_hash=None,
            referral_code=code,
            points=Decimal(row.get("points") or 0),
        )
        result.append(item)
    return result
