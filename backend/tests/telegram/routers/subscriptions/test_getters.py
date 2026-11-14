from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.telegram.routers.subscriptions.getters as getters
from app.core.constants import USER_KEY
from app.core.enums import Locale, SubscriptionStatus
from app.modules.dialogs import catalog
from app.modules.dialogs.flows.menu import register_menu_metadata
from app.modules.transactions import RecurringPaymentState
from app.telegram.dialogs.context import (
    SELECTED_SUBSCRIPTION_KEY,
    build_condition_data,
    menu_flags,
    selected_subscription_id,
)
from app.telegram.i18n import build_translator_hub
from app.telegram.routers.subscriptions.getters import (
    _recurring_card_notice,
    device_confirm_delete_getter,
    subscription_recurring_terms_getter,
)
from tests.seeded_translations import seeded_fluent_source


@pytest.fixture(autouse=True)
def _menu_catalog():
    catalog._reset_for_tests()
    register_menu_metadata()
    yield
    catalog._reset_for_tests()


def _user() -> MagicMock:
    user = MagicMock(
        id=1,
        telegram_id=42,
        points=0,
        bonus_days=0,
        language=Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        loyalty_discount=0,
    )
    user.name = "Test"
    return user


def _subscription(id: int, url: str) -> MagicMock:
    return MagicMock(id=id, url=url, status=SubscriptionStatus.ACTIVE, effective_device_limit=1)


async def test_condition_data_uses_the_selected_subscription() -> None:
    first = _subscription(1, "https://a")
    second = _subscription(2, "https://b")
    active = [first, second]
    trial = AsyncMock(return_value=MagicMock(is_trial_available=False, plan=None))

    data = await build_condition_data(_user(), active, trial, cabinet_url="", selected_id=2)

    assert data["connect_url"] == "https://b"
    assert data["subscriptions_count"] == 2


async def test_condition_data_without_a_selection_uses_the_first_subscription() -> None:
    active = [_subscription(1, "https://a"), _subscription(2, "https://b")]
    trial = AsyncMock(return_value=MagicMock(is_trial_available=False, plan=None))

    data = await build_condition_data(_user(), active, trial, cabinet_url="")

    assert data["connect_url"] == "https://a"


async def test_condition_data_for_a_gone_selection_has_no_subscription() -> None:
    # falling back to another subscription would put its connect link on this card
    active = [_subscription(1, "https://a")]
    trial = AsyncMock(return_value=MagicMock(is_trial_available=False, plan=None))

    data = await build_condition_data(_user(), active, trial, cabinet_url="", selected_id=9)

    assert data["subscription"] is None
    assert data["connect_url"] == ""
    assert data["has_device_limit"] is False


def test_selected_id_prefers_dialog_data_over_start_data() -> None:
    manager = MagicMock(
        dialog_data={SELECTED_SUBSCRIPTION_KEY: 8}, start_data={SELECTED_SUBSCRIPTION_KEY: 7}
    )
    assert selected_subscription_id(manager) == 8


def test_selected_id_falls_back_to_start_data() -> None:
    manager = MagicMock(dialog_data={}, start_data={SELECTED_SUBSCRIPTION_KEY: 7})
    assert selected_subscription_id(manager) == 7


def test_selected_id_is_none_without_a_selection() -> None:
    assert selected_subscription_id(MagicMock(dialog_data={}, start_data=None)) is None


def _settings(max_active: Optional[int], referral_enabled: bool) -> tuple[MagicMock, MagicMock]:
    shop = MagicMock()
    shop.system = AsyncMock(return_value=MagicMock(max_active_subscriptions=max_active))
    referral = MagicMock()
    referral.system = AsyncMock(return_value=MagicMock(enabled=referral_enabled))
    return shop, referral


@pytest.mark.parametrize(
    ("max_active", "paid", "trials", "expected"),
    [(None, 5, 0, True), (3, 2, 0, True), (3, 3, 0, False), (1, 0, 1, True)],
)
async def test_menu_flags_can_purchase_below_the_cap(
    max_active: Optional[int], paid: int, trials: int, expected: bool
) -> None:
    shop, referral = _settings(max_active, referral_enabled=True)
    active = [MagicMock(is_trial=False)] * paid + [MagicMock(is_trial=True)] * trials

    can_purchase, referral_enabled, single = await menu_flags(active, shop, referral)

    assert can_purchase is expected
    assert referral_enabled is True
    assert single is (max_active == 1)


async def test_device_confirm_getter_routes_message_text_through_resolve_variable_kwargs(
    monkeypatch,
) -> None:
    # a saved { $name } in msg-menu-devices-confirm-delete must resolve to its
    # default, so the getter supplies every registered catalog variable
    assert "user_name" in catalog.variable_keys()

    dialog_manager = MagicMock()
    dialog_manager.middleware_data = {
        USER_KEY: MagicMock(
            id=1, language=Locale.EN, personal_discount=0, purchase_discount=0, loyalty_discount=0
        )
    }

    async def _fake_render(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.telegram.routers.subscriptions.getters.render_dialog_buttons", _fake_render
    )

    captured_kwargs: dict[str, object] = {}

    def _fake_get(key: str, **kwargs: object) -> str:
        captured_kwargs.update(kwargs)
        return key

    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=_fake_get)

    data = await device_confirm_delete_getter.__dishka_orig_func__(
        dialog_manager=dialog_manager,
        i18n=i18n,
        dialog_config_cache=MagicMock(),
    )

    assert "user_name" in captured_kwargs
    # with_window_banner reads the text from window_text
    assert "window_text" in data


async def test_a_trial_is_not_offered_to_an_owner_of_a_subscription() -> None:
    offered = AsyncMock(
        return_value=MagicMock(
            is_trial_available=True, plan=MagicMock(), is_free=True, currency=None
        )
    )

    newcomer = await build_condition_data(_user(), [], offered, cabinet_url="")
    # an expired subscription is not in `active`, and still counts
    owner = await build_condition_data(_user(), [], offered, cabinet_url="", owned_count=1)

    assert newcomer["trial_available"] is True
    assert owner["trial_available"] is False
    assert owner["trial_paid_available"] is False
    assert owner["subscriptions_count"] == 1


@pytest.mark.parametrize(
    ("enabled", "current", "accepted", "expected"),
    [
        (False, "Current terms before consent", None, "Current terms before consent"),
        (True, "Changed terms", "Accepted terms", "Accepted terms"),
        (False, None, "Accepted paused terms", "Accepted paused terms"),
    ],
)
async def test_subscription_terms_can_be_read_before_enabling_and_while_paused(
    enabled,
    current,
    accepted,
    expected,
):
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: _user()}
    manager.dialog_data = {SELECTED_SUBSCRIPTION_KEY: 7}
    manager.start_data = {}
    state = SimpleNamespace(
        enabled=enabled,
        terms=SimpleNamespace(text=current) if current else None,
        accepted_terms=SimpleNamespace(text=accepted) if accepted else None,
    )
    hub = MagicMock()
    hub.get_translator_by_locale.return_value = MagicMock(get=lambda key, **kwargs: key)
    result = await subscription_recurring_terms_getter.__dishka_orig_func__(
        manager, get_own_recurring_payment=AsyncMock(return_value=state), i18n=hub
    )
    assert result["window_text"] == expected


def test_retry_notice_shows_the_reason_and_actual_next_attempt():
    hub = build_translator_hub([Locale.RU], {Locale.RU: seeded_fluent_source(Locale.RU)}, Locale.RU)
    state = RecurringPaymentState(
        subscription_id=1,
        enabled=True,
        available=True,
        retrying=True,
        next_retry_at=datetime(2026, 11, 15, 13, 0, tzinfo=timezone.utc),
        amount_limit=Decimal("500"),
        currency="RUB",
        duration_days=30,
        last_error="insufficient_funds",
    )
    text = _recurring_card_notice(state, hub.get_translator_by_locale(Locale.RU.value))
    assert "повторная оплата" in text
    assert "недостаточно средств" in text
    assert "15.11.2026 13:00 UTC" in text


async def test_paused_subscription_keeps_the_withdrawal_button(monkeypatch):
    user = _user()
    subscription = _subscription(7, "https://example.test/subscription")
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: user}
    manager.dialog_data = {SELECTED_SUBSCRIPTION_KEY: subscription.id}
    manager.start_data = {}
    state = RecurringPaymentState(
        subscription_id=subscription.id,
        enabled=False,
        available=False,
        can_disable=True,
        paused=True,
        last_error="payment_status_unknown",
    )
    monkeypatch.setattr(
        getters, "build_condition_data", AsyncMock(return_value={"subscription": subscription})
    )
    monkeypatch.setattr(getters, "window_banner", AsyncMock(return_value=None))
    monkeypatch.setattr(getters, "render_dialog_buttons", AsyncMock(return_value=[]))
    monkeypatch.setattr(getters, "render_window_text", lambda *args, **kwargs: "Subscription")
    hub = build_translator_hub([Locale.EN], {Locale.EN: seeded_fluent_source(Locale.EN)}, Locale.EN)
    result = await getters.subscription_card_getter.__dishka_orig_func__(
        manager,
        config=MagicMock(),
        get_banner=AsyncMock(),
        list_own_subscriptions=AsyncMock(return_value=[subscription]),
        get_available_trial=AsyncMock(),
        i18n=hub,
        dialog_config_cache=MagicMock(),
        get_own_recurring_payment=AsyncMock(return_value=state),
    )
    assert result["auto_renew_off"] is True and result["auto_renew_on"] is False
    assert result["auto_renew_text"] == hub.get_translator_by_locale(Locale.EN.value).get(
        "btn-recurring.disable"
    )
