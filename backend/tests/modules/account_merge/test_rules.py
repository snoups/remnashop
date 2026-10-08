from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.account_merge.dto import MergeConflictDto, MergeLinksDto
from app.modules.account_merge.rules import (
    compute_conflicts,
    conflicts_fingerprint,
    merged_user_fields,
    resolve_sides,
)
from app.modules.users.dto import UserDto

_NO_LINKS = MergeLinksDto(
    source_referrer_id=None, target_referrer_id=None, source_oauth={}, target_oauth={}
)


def _user(**fields: object) -> UserDto:
    return UserDto(**{"id": 1, "name": "n", **fields})


def test_conflict_only_when_both_set_and_different() -> None:
    source = _user(id=1, telegram_id=10, email="a@x.io", name="same")
    target = _user(id=2, telegram_id=20, email=None, name="same")

    keys = [c.key for c in compute_conflicts(source, target, _NO_LINKS)]

    assert keys == ["telegram"]


def test_staff_side_forces_login() -> None:
    source = _user(id=1, login="cust", role=Role.USER)
    target = _user(id=2, login="boss", role=Role.ADMIN)

    [conflict] = compute_conflicts(source, target, _NO_LINKS)

    assert conflict.key == "login" and conflict.forced == "target"


def test_referred_by_and_oauth_conflicts() -> None:
    links = MergeLinksDto(
        source_referrer_id=7,
        target_referrer_id=8,
        source_oauth={"GITHUB": "a"},
        target_oauth={"GITHUB": "b", "OIDC": "c"},
    )

    keys = {c.key for c in compute_conflicts(_user(id=1), _user(id=2), links)}

    assert keys == {"referred_by", "oauth:GITHUB"}


def test_referrer_pointing_at_the_other_side_is_not_a_conflict() -> None:
    links = MergeLinksDto(
        source_referrer_id=2, target_referrer_id=8, source_oauth={}, target_oauth={}
    )

    assert compute_conflicts(_user(id=1), _user(id=2), links) == []


def test_resolve_requires_every_unforced_choice() -> None:
    conflicts = compute_conflicts(
        _user(id=1, email="a@x.io"), _user(id=2, email="b@x.io"), _NO_LINKS
    )

    with pytest.raises(ValidationError) as error:
        resolve_sides(conflicts, {})
    assert error.value.code == ErrorCode.MERGE_CHOICE_MISSING
    assert resolve_sides(conflicts, {"email": "source", "junk": "target"}) == {"email": "source"}


def test_resolve_ignores_choice_for_forced_conflict() -> None:
    conflicts = compute_conflicts(
        _user(id=1, login="c"), _user(id=2, login="b", role=Role.ADMIN), _NO_LINKS
    )

    assert resolve_sides(conflicts, {"login": "source"}) == {"login": "target"}


def test_merged_fields_sum_and_flags() -> None:
    accepted = datetime(2026, 1, 1, tzinfo=timezone.utc)
    source = _user(
        id=1,
        points=Decimal(5),
        bonus_days=3,
        is_trial_available=False,
        is_blocked=True,
        rules_accepted_at=accepted,
        telegram_id=10,
        username="s",
        language=Locale.RU,
    )
    target = _user(id=2, points=Decimal(7), bonus_days=1, is_trial_available=True)

    values = merged_user_fields(source, target, {"language": "source"})

    assert values["points"] == Decimal(12)
    assert values["bonus_days"] == 4
    assert values["is_trial_available"] is False
    assert values["is_blocked"] is True
    assert values["rules_accepted_at"] == accepted
    assert values["telegram_id"] == 10 and values["username"] == "s"
    assert values["language"] == Locale.RU


def test_merged_fields_take_staff_side_privileges() -> None:
    source = _user(id=1, role=Role.OWNER, ip_allowlist=["1.1.1.1"], login="own")
    target = _user(id=2, role=Role.USER, telegram_id=5)

    values = merged_user_fields(source, target, {})

    assert values["role"] == Role.OWNER
    assert values["ip_allowlist"] == ["1.1.1.1"]
    assert values["login"] == "own"
    assert values["telegram_id"] == 5


@pytest.mark.parametrize("owner_side", ["source", "target"])
def test_staff_side_decides_block_flag(owner_side: str) -> None:
    owner = _user(id=1, role=Role.OWNER, is_blocked=False)
    customer = _user(id=2, is_blocked=True)
    source, target = (owner, customer) if owner_side == "source" else (customer, owner)

    assert merged_user_fields(source, target, {})["is_blocked"] is False


def test_staff_side_without_login_keeps_no_login() -> None:
    source = _user(id=1, login="cust", password_hash="h")
    target = _user(id=2, role=Role.ADMIN)

    values = merged_user_fields(source, target, {})

    assert values["login"] is None and values["password_hash"] is None


def test_no_oauth_conflict_when_staff_side_exists() -> None:
    links = MergeLinksDto(
        source_referrer_id=None,
        target_referrer_id=None,
        source_oauth={"GITHUB": "a"},
        target_oauth={"GITHUB": "b"},
    )

    conflicts = compute_conflicts(_user(id=1), _user(id=2, role=Role.ADMIN), links)

    assert [c.key for c in conflicts] == []


def test_fingerprint_is_stable_and_tracks_every_field() -> None:
    base = MergeConflictDto(key="email", source_value="a", target_value="b", forced=None)
    same = MergeConflictDto(key="email", source_value="a", target_value="b", forced=None)
    assert conflicts_fingerprint(
        [base], source_privileged=False, target_privileged=False
    ) == conflicts_fingerprint([same], source_privileged=False, target_privileged=False)
    for changed in (
        MergeConflictDto(key="name", source_value="a", target_value="b", forced=None),
        MergeConflictDto(key="email", source_value="x", target_value="b", forced=None),
        MergeConflictDto(key="email", source_value="a", target_value="x", forced=None),
        MergeConflictDto(key="email", source_value="a", target_value="b", forced="source"),
    ):
        assert conflicts_fingerprint(
            [changed], source_privileged=False, target_privileged=False
        ) != conflicts_fingerprint([base], source_privileged=False, target_privileged=False)


def test_fingerprint_tracks_privileged_flags() -> None:
    conflicts = [MergeConflictDto(key="email", source_value="a", target_value="b", forced=None)]
    seen = {
        conflicts_fingerprint(conflicts, source_privileged=s, target_privileged=t)
        for s in (False, True)
        for t in (False, True)
    }
    assert len(seen) == 4
