from datetime import datetime, timezone
from typing import Optional

import pytest

from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.modules.account_merge.customer import customer_sides, ensure_customer_mergeable
from app.modules.account_merge.dto import MergeLinksDto
from app.modules.users.dto import UserDto


def _user(**fields: object) -> UserDto:
    return UserDto(**{"id": 1, "name": "n", **fields})


def _links(**fields: object) -> MergeLinksDto:
    return MergeLinksDto(
        **{
            "source_referrer_id": None,
            "target_referrer_id": None,
            "source_oauth": {},
            "target_oauth": {},
            **fields,
        }
    )


def _refused(
    current: UserDto, other: UserDto, links: Optional[MergeLinksDto] = None
) -> ConflictError:
    with pytest.raises(ConflictError) as error:
        ensure_customer_mergeable(current, other, links or _links())
    return error.value


def test_staff_other_is_refused() -> None:
    error = _refused(_user(id=1), _user(id=2, login="boss", role=Role.ADMIN))
    assert error.code == ErrorCode.MERGE_ACCOUNT_PRIVILEGED


def test_blocked_other_is_refused() -> None:
    assert (
        _refused(_user(id=1), _user(id=2, is_blocked=True)).code == ErrorCode.MERGE_ACCOUNT_BLOCKED
    )


def test_different_emails_refused() -> None:
    error = _refused(_user(id=1, email="a@x.io"), _user(id=2, email="b@x.io"))
    assert error.code == ErrorCode.MERGE_IDENTITY_CONFLICT and "email" in str(error)


def test_different_telegram_refused() -> None:
    error = _refused(_user(id=1, telegram_id=10), _user(id=2, telegram_id=20))
    assert error.code == ErrorCode.MERGE_IDENTITY_CONFLICT and "telegram" in str(error)


def test_same_provider_different_identity_refused() -> None:
    links = _links(source_oauth={"GITHUB": "a"}, target_oauth={"GITHUB": "b"})
    error = _refused(_user(id=1), _user(id=2), links)
    assert error.code == ErrorCode.MERGE_IDENTITY_CONFLICT and "oauth:GITHUB" in str(error)


def test_empty_side_is_not_a_conflict() -> None:
    ensure_customer_mergeable(
        _user(id=1, email=None), _user(id=2, email="a@x.io", telegram_id=5), _links()
    )


def test_sides_keep_current_name_and_language() -> None:
    current = _user(id=1, name="cur", language=Locale.EN)
    other = _user(id=2, name="oth", language=Locale.RU)

    assert customer_sides(current, other, _links()) == {"name": "target", "language": "target"}


@pytest.mark.parametrize("field", ["personal_discount", "purchase_discount"])
def test_sides_take_bigger_discount(field: str) -> None:
    smaller_current = customer_sides(
        _user(id=1, **{field: 5}), _user(id=2, **{field: 10}), _links()
    )
    bigger_current = customer_sides(
        _user(id=1, **{field: 15}), _user(id=2, **{field: 10}), _links()
    )

    assert smaller_current[field] == "source" and bigger_current[field] == "target"


def test_sides_take_earlier_referrer() -> None:
    early = datetime(2026, 1, 1, tzinfo=timezone.utc)
    late = datetime(2026, 2, 1, tzinfo=timezone.utc)

    def sides(source_at: datetime, target_at: datetime) -> str:
        links = _links(
            source_referrer_id=7,
            target_referrer_id=8,
            source_referred_at=source_at,
            target_referred_at=target_at,
        )
        return customer_sides(_user(id=1), _user(id=2), links)["referred_by"]

    assert sides(early, late) == "source"
    assert sides(late, early) == "target"
    assert sides(early, early) == "target"
