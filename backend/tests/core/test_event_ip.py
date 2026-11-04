from typing import Any, Optional

import pytest

from app.core.actor import SyntheticActor
from app.core.enums import Role
from app.core.events import MASKED_IP, visible_event_ip

IP = "203.0.113.7"


def _reader(role: Role, user_id: int = 100) -> SyntheticActor:
    return SyntheticActor(id=user_id, role=role, name="r", is_privileged=True, log="[r]")


def _acted_by(role: Role, user_id: int = 1, key: str = "actor") -> dict[str, Any]:
    return {key: {"id": user_id, "role": role.name}}


@pytest.mark.parametrize(
    ("reader_role", "owner_role", "expected"),
    [
        (Role.ADMIN, Role.OWNER, MASKED_IP),
        (Role.ADMIN, Role.ADMIN, MASKED_IP),
        (Role.OWNER, Role.ADMIN, IP),
        (Role.ADMIN, Role.USER, IP),
    ],
)
def test_staff_ip_is_shown_only_from_a_higher_role(
    reader_role: Role, owner_role: Role, expected: str
) -> None:
    payload = _acted_by(owner_role, key="user")
    assert visible_event_ip(_reader(reader_role), "LoginSucceededEvent", payload, IP) == expected


def test_own_ip_stays_visible() -> None:
    payload = _acted_by(Role.ADMIN, user_id=100)
    assert visible_event_ip(_reader(Role.ADMIN), "X", payload, IP) == IP


def test_api_token_ip_counts_as_the_owner() -> None:
    payload = _acted_by(Role.USER, user_id=0)
    assert visible_event_ip(_reader(Role.ADMIN), "X", payload, IP) == MASKED_IP


def test_customer_promoted_since_is_masked() -> None:
    payload = _acted_by(Role.USER)
    assert visible_event_ip(_reader(Role.ADMIN), "X", payload, IP, Role.ADMIN) == MASKED_IP


@pytest.mark.parametrize(("reader_role", "expected"), [(Role.ADMIN, MASKED_IP), (Role.OWNER, IP)])
def test_anonymous_staff_sign_in_is_owner_only(reader_role: Role, expected: str) -> None:
    assert visible_event_ip(_reader(reader_role), "LoginFailedEvent", {}, IP) == expected


@pytest.mark.parametrize("ip", [IP, None])
def test_anonymous_customer_side_event_is_untouched(ip: Optional[str]) -> None:
    assert visible_event_ip(_reader(Role.ADMIN), "EmailCodeAttemptsExhaustedEvent", {}, ip) == ip
