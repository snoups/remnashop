from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.core.enums import SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.panel import (
    configure_for_plan,
    new_panel_user,
    restore,
    shop_user_key_from_username,
)
from app.modules.users import UserDto
from tests.modules.subscriptions.factories import make_plan_snapshot

_EXPIRE_AT = datetime(2030, 1, 1, tzinfo=timezone.utc)


def _user(telegram_id: Optional[int] = None, email: Optional[str] = None) -> UserDto:
    now = datetime_now()
    return UserDto(
        id=1, name="buyer", telegram_id=telegram_id, email=email, created_at=now, updated_at=now
    )


def _subscription(status: SubscriptionStatus, expire_at: datetime) -> SubscriptionDto:
    now = datetime_now()
    return SubscriptionDto(
        id=1,
        user_id=1,
        remnawave_user_id=7,
        status=status,
        traffic_limit=100,
        device_limit=3,
        effective_traffic_limit=100,
        effective_device_limit=3,
        expire_at=expire_at,
        url="https://example.com/sub/7",
        plan_snapshot=make_plan_snapshot(),
        created_at=now,
        updated_at=now,
    )


def test_the_plans_tag_goes_onto_the_panel_user() -> None:
    plan = make_plan_snapshot(tag="VIP")

    assert new_panel_user(_user(), plan, _EXPIRE_AT, "rs_").tag == "VIP"
    assert configure_for_plan(7, plan, _EXPIRE_AT).tag == "VIP"


def test_a_plan_without_a_tag_clears_the_panel_users_one() -> None:
    request = configure_for_plan(7, make_plan_snapshot(), _EXPIRE_AT)

    # the SDK drops unset fields only: an explicit None reaches the panel as null
    assert request.model_dump(exclude_unset=True)["tag"] is None


def test_the_panel_user_carries_the_buyers_telegram_and_email() -> None:
    request = new_panel_user(
        _user(telegram_id=42, email="a@b.c"), make_plan_snapshot(), _EXPIRE_AT, "rs_"
    )

    assert request.telegram_id == 42
    assert request.email == "a@b.c"


def test_nothing_the_panel_refuses_as_null_is_sent_as_null() -> None:
    # a plan without squads, a change that keeps the panel's status
    plan = make_plan_snapshot()
    sent = [
        new_panel_user(_user(), plan, _EXPIRE_AT, "rs_").model_dump(exclude_unset=True),
        configure_for_plan(7, plan, _EXPIRE_AT).model_dump(exclude_unset=True),
    ]

    for body in sent:
        assert "status" not in body
        assert "active_internal_squads" not in body
        assert "telegram_id" not in body and "email" not in body


def test_restore_leaves_out_a_past_expiry_the_panel_would_refuse() -> None:
    expired = _subscription(SubscriptionStatus.EXPIRED, datetime_now() - timedelta(days=1))
    live = _subscription(SubscriptionStatus.ACTIVE, datetime_now() + timedelta(days=1))

    assert "expire_at" not in restore(expired).model_dump(exclude_unset=True)
    assert restore(live).expire_at == live.expire_at


@pytest.mark.parametrize(
    "username",
    ["rs_99999999999999999999", "rs_web_9999999999", "rs_9999999999_abcdef12"],
)
def test_out_of_range_panel_username_matches_no_shop_user(username: str) -> None:
    assert shop_user_key_from_username(username, "rs_") is None


def test_in_range_panel_usernames_still_match() -> None:
    assert shop_user_key_from_username("rs_9999999999", "rs_") == ("telegram_id", 9999999999)
    assert shop_user_key_from_username("rs_web_2147483647", "rs_") == ("id", 2147483647)


def test_a_custom_prefix_reads_only_its_own_names() -> None:
    assert shop_user_key_from_username("shopb_5_0123abcd", "shopb_") == ("id", 5)
    assert shop_user_key_from_username("shopb_89081", "shopb_") == ("telegram_id", 89081)
    assert shop_user_key_from_username("rs_5_0123abcd", "shopb_") is None
    assert shop_user_key_from_username("rs_89081", "shopb_") is None


def test_new_panel_user_is_named_with_the_prefix() -> None:
    username = new_panel_user(_user(), make_plan_snapshot(), _EXPIRE_AT, "shopb_").username
    assert username is not None and username.startswith("shopb_")
