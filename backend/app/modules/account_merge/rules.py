import hashlib
import json
from typing import Callable, Final, Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.account_merge.dto import (
    MergeConflictDto,
    MergeConflictKey,
    MergedUserDto,
    MergeLinksDto,
    MergeSide,
    oauth_conflict_key,
)
from app.modules.users import UserDto

# what decides "has a value" for each field conflict; the columns that travel
# with it are taken together in merged_user_fields
_FIELD_CONFLICTS: Final[tuple[tuple[MergeConflictKey, Callable[[UserDto], object]], ...]] = (
    (MergeConflictKey.TELEGRAM, lambda user: user.telegram_id),
    (MergeConflictKey.EMAIL, lambda user: user.email),
    (MergeConflictKey.LOGIN, lambda user: user.login),
    (MergeConflictKey.NAME, lambda user: user.name),
    (MergeConflictKey.LANGUAGE, lambda user: user.language),
    (MergeConflictKey.PERSONAL_DISCOUNT, lambda user: user.personal_discount),
    (MergeConflictKey.PURCHASE_DISCOUNT, lambda user: user.purchase_discount),
)
_VALUE_OF: Final[dict[MergeConflictKey, Callable[[UserDto], object]]] = dict(_FIELD_CONFLICTS)


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


def referrer_candidates(
    source: UserDto, target: UserDto, links: MergeLinksDto
) -> dict[MergeSide, int]:
    # a link to the other side is deleted, not chosen; a shared referrer counts once
    candidates: dict[MergeSide, int] = {}
    if links.target_referrer_id is not None and links.target_referrer_id != source.id:
        candidates["target"] = links.target_referrer_id
    if (
        links.source_referrer_id is not None
        and links.source_referrer_id != target.id
        and links.source_referrer_id != candidates.get("target")
    ):
        candidates["source"] = links.source_referrer_id
    return candidates


def compute_conflicts(
    source: UserDto, target: UserDto, links: MergeLinksDto
) -> list[MergeConflictDto]:
    staff = _staff_side(source, target)
    conflicts: list[MergeConflictDto] = []
    for key, value_of in _FIELD_CONFLICTS:
        source_value, target_value = value_of(source), value_of(target)
        if _is_set(source_value) and _is_set(target_value) and source_value != target_value:
            conflicts.append(
                MergeConflictDto(
                    key=key,
                    source_value=_label(source_value),
                    target_value=_label(target_value),
                    forced=staff if key is MergeConflictKey.LOGIN else None,
                )
            )

    referrers = referrer_candidates(source, target, links)
    if len(referrers) == 2:
        conflicts.append(
            MergeConflictDto(
                key=MergeConflictKey.REFERRED_BY,
                source_value=_label(referrers["source"]),
                target_value=_label(referrers["target"]),
            )
        )

    # the customer's identities are dropped when merging with staff
    providers = set() if staff else links.source_oauth.keys() & links.target_oauth.keys()
    for provider in sorted(providers):
        conflicts.append(
            MergeConflictDto(
                key=oauth_conflict_key(provider),
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
) -> MergedUserDto:
    staff_side = _staff_side(source, target)
    staff = source if staff_side == "source" else target

    def winner(key: MergeConflictKey) -> UserDto:
        if key is MergeConflictKey.LOGIN and staff_side is not None:
            return staff
        side = sides.get(key)
        if side is None:
            return target if _is_set(_VALUE_OF[key](target)) else source
        return source if side == "source" else target

    telegram = winner(MergeConflictKey.TELEGRAM)
    email = winner(MergeConflictKey.EMAIL)
    login = winner(MergeConflictKey.LOGIN)
    personal = winner(MergeConflictKey.PERSONAL_DISCOUNT)
    purchase = winner(MergeConflictKey.PURCHASE_DISCOUNT)
    return MergedUserDto(
        telegram_id=telegram.telegram_id,
        username=telegram.username,
        email=email.email,
        email_undeliverable_at=email.email_undeliverable_at,
        login=login.login,
        password_hash=login.password_hash,
        password_change_required=login.password_change_required,
        name=winner(MergeConflictKey.NAME).name,
        language=winner(MergeConflictKey.LANGUAGE).language,
        personal_discount=personal.personal_discount,
        personal_discount_promocode_id=personal.personal_discount_promocode_id,
        purchase_discount=purchase.purchase_discount,
        purchase_discount_promocode_id=purchase.purchase_discount_promocode_id,
        # the staff side keeps its role, grants and notification setup
        role=staff.role,
        permission_grants=staff.permission_grants,
        permission_revokes=staff.permission_revokes,
        ip_allowlist=staff.ip_allowlist,
        notification_channels=staff.notification_channels,
        notifications_seen_at=staff.notifications_seen_at,
        notifications_cleared_at=staff.notifications_cleared_at,
        points=source.points + target.points,
        bonus_days=source.bonus_days + target.bonus_days,
        # a spent trial stays spent
        is_trial_available=source.is_trial_available and target.is_trial_available,
        # a blocked customer must not lock staff out
        is_blocked=staff.is_blocked if staff_side else source.is_blocked or target.is_blocked,
        marketing_opt_out=source.marketing_opt_out or target.marketing_opt_out,
        loyalty_excluded=source.loyalty_excluded or target.loyalty_excluded,
    )
