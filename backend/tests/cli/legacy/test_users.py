from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.cli.legacy.report import MigrationReport
from app.cli.legacy.users import transform_users
from app.core.enums import Role
from app.core.utils.email import canonical_email

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _row(user_id: int, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": user_id,
        "telegram_id": 1000 + user_id,
        "username": None,
        "email": None,
        "is_email_verified": False,
        "password_hash": "scrypt$x",
        "referral_code": f"CODE{user_id:04d}",
        "name": f"user{user_id}",
        "role": "USER",
        "language": "RU",
        "personal_discount": 0,
        "purchase_discount": 0,
        "points": 0,
        "is_blocked": False,
        "is_bot_blocked": False,
        "is_rules_accepted": True,
        "is_trial_available": True,
        "ad_link_id": None,
        "referral_code_reset_at": None,
        "current_subscription_id": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(overrides)
    return row


def _run(
    rows: list[dict[str, Any]],
    *,
    bot_owner_id: Optional[int] = None,
    live: Optional[set[int]] = None,
) -> tuple[dict[int, dict[str, Any]], MigrationReport]:
    report = MigrationReport()
    result = transform_users(
        rows, bot_owner_id=bot_owner_id, live_subscription_user_ids=live or set(), report=report
    )
    return {item["id"]: item for item in result}, report


def test_roles_map_by_name() -> None:
    rows = [
        _row(1, role="USER"),
        _row(2, role="PREVIEW"),
        _row(3, role="ADMIN"),
        _row(4, role="DEV"),
    ]
    out, _ = _run(rows)
    assert [out[i]["role"] for i in (1, 2, 3, 4)] == [Role.USER, Role.USER, Role.ADMIN, Role.ADMIN]


def test_owner_from_bot_owner_id() -> None:
    rows = [_row(1, role="OWNER"), _row(5, role="OWNER", telegram_id=555)]
    out, _ = _run(rows, bot_owner_id=555)
    assert out[5]["role"] == Role.OWNER
    assert out[1]["role"] == Role.ADMIN


def test_owner_falls_back_to_first_owner() -> None:
    rows = [_row(5, role="OWNER"), _row(1, role="OWNER")]
    out, _ = _run(rows)
    assert out[1]["role"] == Role.OWNER
    assert out[5]["role"] == Role.ADMIN


def test_no_owner_at_all() -> None:
    out, report = _run([_row(1, role="ADMIN")], bot_owner_id=999)
    assert all(item["role"] != Role.OWNER for item in out.values())
    assert any("bootstrap" in note for note in report.notes)


def test_email_lowercased_unverified_kept() -> None:
    out, _ = _run([_row(1, email="Foo@Mail.RU", is_email_verified=False)])
    assert out[1]["email"] == "foo@mail.ru"
    assert out[1]["email_canonical"] == canonical_email("foo@mail.ru")


def test_canonical_email_collision() -> None:
    rows = [_row(1, email="ab@gmail.com"), _row(2, email="a.b@gmail.com")]
    out, report = _run(rows, live={2})
    assert out[2]["email"] == "a.b@gmail.com"
    assert out[1]["email"] is None and out[1]["email_canonical"] is None
    assert [(s.table, s.source_id) for s in report.skips] == [("users", "1")]


def test_canonical_email_collision_lowest_id_without_live() -> None:
    rows = [_row(2, email="a.b@gmail.com"), _row(1, email="ab@gmail.com")]
    out, _ = _run(rows)
    assert out[1]["email"] == "ab@gmail.com"
    assert out[2]["email"] is None


def test_password_not_migrated() -> None:
    out, _ = _run([_row(1), _row(2, role="OWNER")])
    assert all(item["password_hash"] is None for item in out.values())


def test_long_referral_code_regenerated() -> None:
    out, report = _run([_row(1, referral_code="X" * 20), _row(2)])
    assert len(out[1]["referral_code"]) <= 16
    assert out[1]["referral_code"] != out[2]["referral_code"]
    assert any("referral" in note for note in report.notes)


def test_points_to_decimal() -> None:
    out, _ = _run([_row(1, points=42)])
    assert out[1]["points"] == Decimal(42)
    assert isinstance(out[1]["points"], Decimal)


def test_rules_and_current_subscription_dropped() -> None:
    out, _ = _run([_row(1, current_subscription_id=7)])
    assert "is_rules_accepted" not in out[1]
    assert "current_subscription_id" not in out[1]
