from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.modules.account_merge.dto import MergeLinksDto, MergeSide
from app.modules.account_merge.rules import REFERRED_BY, compute_conflicts
from app.modules.users import UserDto

# identities that can't be reconciled: the customer has to unlink one first
_IDENTITY_KEYS = ("telegram", "email", "oauth:")


def ensure_customer_mergeable(current: UserDto, other: UserDto, links: MergeLinksDto) -> None:
    if other.is_privileged:
        raise ConflictError(
            "Staff account can't be merged", code=ErrorCode.MERGE_ACCOUNT_PRIVILEGED
        )
    if other.is_blocked:
        raise ConflictError("Account is blocked", code=ErrorCode.MERGE_ACCOUNT_BLOCKED)
    for conflict in compute_conflicts(other, current, links):
        if conflict.key.startswith(_IDENTITY_KEYS):
            raise ConflictError(
                f"A different '{conflict.key}' is already linked",
                code=ErrorCode.MERGE_IDENTITY_CONFLICT,
            )


def customer_sides(current: UserDto, other: UserDto, links: MergeLinksDto) -> dict[str, MergeSide]:
    sides: dict[str, MergeSide] = {}
    for conflict in compute_conflicts(other, current, links):
        key = conflict.key
        if key in ("name", "language"):
            sides[key] = "target"
        elif key in ("personal_discount", "purchase_discount"):
            sides[key] = "source" if getattr(other, key) > getattr(current, key) else "target"
        elif key == REFERRED_BY:
            earlier = (
                links.source_referred_at is not None
                and links.target_referred_at is not None
                and links.source_referred_at < links.target_referred_at
            )
            sides[key] = "source" if earlier else "target"
    return sides
