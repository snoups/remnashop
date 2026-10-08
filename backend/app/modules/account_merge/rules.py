import hashlib
import json
from typing import Final, Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.account_merge.dto import MergeConflictDto, MergeLinksDto, MergeSide
from app.modules.users import UserDto

# conflict key -> columns that travel together; the first one decides "has a value"
FIELD_CONFLICTS: Final[dict[str, tuple[str, ...]]] = {
    "telegram": ("telegram_id", "username"),
    "email": ("email",),
    "login": ("login", "password_hash", "password_change_required"),
    "name": ("name",),
    "language": ("language",),
    "personal_discount": ("personal_discount", "personal_discount_promocode_id"),
    "purchase_discount": ("purchase_discount", "purchase_discount_promocode_id"),
}
REFERRED_BY: Final[str] = "referred_by"
OAUTH_PREFIX: Final[str] = "oauth:"
STAFF_FIELDS: Final[tuple[str, ...]] = (
    "role",
    "permission_grants",
    "permission_revokes",
    "ip_allowlist",
    "notification_channels",
    "notifications_seen_at",
    "notifications_cleared_at",
)


def _is_set(value: object) -> bool:
    return value is not None and value != "" and value != 0


def _label(value: object) -> Optional[str]:
    return None if value is None else str(value)


def _staff_side(source: UserDto, target: UserDto) -> Optional[MergeSide]:
    if source.is_privileged:
        return "source"
    if target.is_privileged:
        return "target"
    return None


def compute_conflicts(
    source: UserDto, target: UserDto, links: MergeLinksDto
) -> list[MergeConflictDto]:
    staff = _staff_side(source, target)
    conflicts: list[MergeConflictDto] = []
    for key, fields in FIELD_CONFLICTS.items():
        source_value, target_value = getattr(source, fields[0]), getattr(target, fields[0])
        if _is_set(source_value) and _is_set(target_value) and source_value != target_value:
            conflicts.append(
                MergeConflictDto(
                    key=key,
                    source_value=_label(source_value),
                    target_value=_label(target_value),
                    forced=staff if key == "login" else None,
                )
            )

    # a link to the other side is deleted, not chosen
    source_referrer = None if links.source_referrer_id == target.id else links.source_referrer_id
    target_referrer = None if links.target_referrer_id == source.id else links.target_referrer_id
    if (
        source_referrer is not None
        and target_referrer is not None
        and source_referrer != target_referrer
    ):
        conflicts.append(
            MergeConflictDto(
                key=REFERRED_BY,
                source_value=_label(source_referrer),
                target_value=_label(target_referrer),
            )
        )

    # the customer's identities are dropped when merging with staff
    providers = set() if staff else links.source_oauth.keys() & links.target_oauth.keys()
    for provider in sorted(providers):
        conflicts.append(
            MergeConflictDto(
                key=f"{OAUTH_PREFIX}{provider}",
                source_value=links.source_oauth[provider],
                target_value=links.target_oauth[provider],
            )
        )
    return conflicts


def conflicts_fingerprint(
    conflicts: list[MergeConflictDto], *, source_privileged: bool, target_privileged: bool
) -> str:
    payload = json.dumps(
        [
            [[c.key, c.source_value, c.target_value, c.forced] for c in conflicts],
            source_privileged,
            target_privileged,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def resolve_sides(
    conflicts: list[MergeConflictDto], choices: dict[str, MergeSide]
) -> dict[str, MergeSide]:
    sides: dict[str, MergeSide] = {}
    for conflict in conflicts:
        side = conflict.forced or choices.get(conflict.key)
        if side is None:
            raise ValidationError(
                f"No choice for conflict '{conflict.key}'", code=ErrorCode.MERGE_CHOICE_MISSING
            )
        sides[conflict.key] = side
    return sides


def merged_user_fields(
    source: UserDto, target: UserDto, sides: dict[str, MergeSide]
) -> dict[str, object]:
    staff_side = _staff_side(source, target)
    staff = source if staff_side == "source" else target
    values: dict[str, object] = {}
    for key, fields in FIELD_CONFLICTS.items():
        side = sides.get(key)
        if key == "login" and staff_side is not None:
            winner = staff
        elif side is None:
            winner = target if _is_set(getattr(target, fields[0])) else source
        else:
            winner = source if side == "source" else target
        for name in fields:
            values[name] = getattr(winner, name)

    for name in STAFF_FIELDS:
        values[name] = getattr(staff, name)

    accepted = [d for d in (source.rules_accepted_at, target.rules_accepted_at) if d is not None]
    values.update(
        points=source.points + target.points,
        bonus_days=source.bonus_days + target.bonus_days,
        # a spent trial stays spent
        is_trial_available=source.is_trial_available and target.is_trial_available,
        # a blocked customer must not lock staff out
        is_blocked=staff.is_blocked if staff_side else source.is_blocked or target.is_blocked,
        marketing_opt_out=source.marketing_opt_out or target.marketing_opt_out,
        loyalty_excluded=source.loyalty_excluded or target.loyalty_excluded,
        rules_accepted_at=max(accepted) if accepted else None,
    )
    return values
