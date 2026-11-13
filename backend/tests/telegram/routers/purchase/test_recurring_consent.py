from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Format

from app.core.enums import Currency, Locale, PurchaseType
from app.modules.transactions.recurring_terms import build_recurring_terms
from app.telegram.routers.purchase.dialog import confirm, recurring_terms
from app.telegram.routers.purchase.getters import confirm_getter, recurring_terms_getter
from app.telegram.routers.purchase.handlers import (
    PAYMENT_URL_KEY,
    RECURRING_ACCEPTED_KEY,
    RECURRING_TERMS_KEY,
    _store_method,
    checkout_data,
    on_recurring_choice,
)
from tests.telegram.routers.purchase.test_getters import _CATALOG, _PRICED, _i18n, _manager


def _terms(config, *, amount="500"):
    return build_recurring_terms(
        config=config,
        user_id=1,
        plan_id=10,
        target_subscription_id=None,
        purchase_type=PurchaseType.NEW,
        initial_amount=Decimal("199"),
        amount_limit=Decimal(amount),
        currency=Currency.RUB,
        duration_days=30,
        locale=Locale.RU,
    )


def _checkout_manager():
    manager = _manager(
        {
            **_PRICED,
            "prices": dict(_PRICED["prices"]),
            "plan_name": "Plan 10",
            "currency": "RUB",
            "gateway_type": "YOOKASSA",
            "recurring_available": True,
        }
    )
    manager.start_data = {}
    return manager


async def _render(manager, terms):
    return await confirm_getter.__dishka_orig_func__(
        manager,
        list_active_plans=AsyncMock(return_value=_CATALOG),
        list_own_subscriptions=AsyncMock(return_value=[]),
        list_visible_legal_documents=MagicMock(execute=AsyncMock(return_value=[])),
        get_recurring_terms=AsyncMock(return_value=terms),
        i18n=_i18n(),
    )


async def _choice(manager, enabled=True):
    manager.item_id = manager.dialog_data[RECURRING_TERMS_KEY]["terms_id"][:16]
    await on_recurring_choice(
        AsyncMock(id="consent-click"),
        Button(Format("x"), id="recurring_on" if enabled else "recurring_off"),
        manager,
    )


async def test_confirmation_starts_unchecked_and_only_shows_terms_after_consent(config):
    manager = _checkout_manager()
    terms = _terms(config)
    before = await _render(manager, terms)
    assert before["recurring_on"] and not before["recurring_off"]
    assert not before["recurring_terms"]
    assert terms.summary in before["window_text"]
    assert not checkout_data(manager).recurring_consent
    manager.is_preview.return_value = False
    manager.current_context.return_value.stack_id = ""
    manager.current_context.return_value.id = "test"
    keyboard = await confirm.render_kbd(before, manager)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "btn-recurring.terms" not in labels
    await _choice(manager)
    after = await _render(manager, terms)
    assert not after["recurring_on"] and after["recurring_off"] and after["recurring_terms"]
    keyboard = await confirm.render_kbd(after, manager)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "btn-recurring.terms" in labels
    assert all(
        len(button.callback_data.encode()) <= 64
        for row in keyboard.inline_keyboard
        for button in row
    )
    checkout = checkout_data(manager)
    assert checkout.recurring_consent and checkout.recurring_terms_id == terms.terms_id
    assert checkout.consent_event_id == "consent-click"


async def test_repeated_disable_clicks_do_not_restore_consent(config):
    manager = _checkout_manager()
    await _render(manager, _terms(config))
    await _choice(manager)
    await _choice(manager, False)
    await _choice(manager, False)
    result = await _render(manager, _terms(config))
    assert not result["recurring_terms"] and not checkout_data(manager).recurring_consent


async def test_changed_terms_clear_the_previous_checkbox(config):
    manager = _checkout_manager()
    await _render(manager, _terms(config))
    await _choice(manager)
    result = await _render(manager, _terms(config, amount="600"))
    assert not result["recurring_terms"] and not checkout_data(manager).recurring_consent
    assert "600" in result["window_text"]


async def test_method_selection_resets_consent_and_the_old_payment_link(config):
    manager = _checkout_manager()
    await _render(manager, _terms(config))
    await _choice(manager)
    manager.dialog_data[PAYMENT_URL_KEY] = "https://old-payment"
    _store_method(manager.dialog_data, {"gateway_type": "YOOKASSA", "currency": "RUB"})
    assert RECURRING_ACCEPTED_KEY not in manager.dialog_data
    assert RECURRING_TERMS_KEY not in manager.dialog_data
    assert PAYMENT_URL_KEY not in manager.dialog_data


async def test_terms_button_displays_the_same_text_without_clearing_consent(config):
    manager = _checkout_manager()
    terms = _terms(config)
    await _render(manager, terms)
    await _choice(manager)
    result = await recurring_terms_getter.__dishka_orig_func__(manager, i18n=_i18n())
    assert result["window_text"] == terms.text
    assert manager.dialog_data[RECURRING_ACCEPTED_KEY] == terms.terms_id


async def test_unavailable_recurring_payments_hide_both_buttons_and_clear_consent(config):
    manager = _checkout_manager()
    await _render(manager, _terms(config))
    await _choice(manager)
    result = await _render(manager, None)
    assert not any(result[key] for key in ("recurring_on", "recurring_off", "recurring_terms"))
    assert not checkout_data(manager).recurring_consent


async def test_full_terms_are_rendered_without_a_media_caption(config):
    terms = _terms(config)
    assert terms.text
    manager = _checkout_manager()
    await _render(manager, terms)
    await _choice(manager)
    data = await recurring_terms_getter.__dishka_orig_func__(manager, i18n=_i18n())
    assert await recurring_terms.render_media(data, manager) is None
    text = await recurring_terms.render_text(data, manager)
    assert text == terms.text and len(text) <= 4096


async def test_a_stale_checkbox_cannot_accept_replacement_terms(config):
    manager = _checkout_manager()
    old = _terms(config)
    await _render(manager, old)
    await _render(manager, _terms(config, amount="600"))
    manager.item_id = old.terms_id[:16]
    await on_recurring_choice(
        AsyncMock(id="stale-click"), Button(Format("x"), id="recurring_on"), manager
    )
    assert RECURRING_ACCEPTED_KEY not in manager.dialog_data
    assert not checkout_data(manager).recurring_consent
