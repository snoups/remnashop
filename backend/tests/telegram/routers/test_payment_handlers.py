from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import PreCheckoutQuery

from app.telegram.routers.payments.handlers import on_pre_checkout, on_successful_payment


def _i18n() -> MagicMock:
    hub = MagicMock()
    hub.root_locale = "en"
    hub.translators_map = {"en": ["en"]}
    hub.get_translator_by_locale.return_value.get.side_effect = lambda key: key
    return hub


def _query(language_code: str = "en") -> AsyncMock:
    query = AsyncMock(spec=PreCheckoutQuery)
    query.answer = AsyncMock()
    query.from_user = MagicMock(id=5, language_code=language_code)
    query.invoice_payload = "ref"
    query.currency = "XTR"
    query.total_amount = 50
    return query


async def test_pre_checkout_answers_the_usecase_verdict() -> None:
    query = _query()
    validate = AsyncMock()
    validate.system.return_value = False

    await on_pre_checkout(query, validate, _i18n())

    query.answer.assert_awaited_once_with(ok=False, error_message="ntf-purchase.stars-rejected")


async def test_pre_checkout_approves_a_valid_order() -> None:
    query = _query()
    validate = AsyncMock()
    validate.system.return_value = True

    await on_pre_checkout(query, validate, _i18n())

    query.answer.assert_awaited_once_with(ok=True)
    dto = validate.system.await_args.args[0]
    assert (dto.telegram_id, dto.payload, dto.currency, dto.total_amount) == (5, "ref", "XTR", 50)


async def test_pre_checkout_unserved_language_falls_back_to_root_locale() -> None:
    query = _query("xx")
    validate = AsyncMock()
    validate.system.return_value = False
    hub = _i18n()

    await on_pre_checkout(query, validate, hub)

    hub.get_translator_by_locale.assert_called_once_with("en")


def _paid_message() -> MagicMock:
    message = MagicMock()
    message.from_user = MagicMock(id=5)
    message.successful_payment = MagicMock(
        invoice_payload="ref", currency="XTR", total_amount=50, telegram_payment_charge_id="c"
    )
    return message


async def test_successful_payment_is_settled_in_place() -> None:
    confirm = AsyncMock()
    dispatch = AsyncMock()

    await on_successful_payment(_paid_message(), confirm, dispatch)

    dto = confirm.system.await_args.args[0]
    assert (dto.telegram_id, dto.payload, dto.currency, dto.total_amount, dto.charge_id) == (
        5,
        "ref",
        "XTR",
        50,
        "c",
    )
    dispatch.kiq.assert_not_awaited()


async def test_successful_payment_falls_back_to_the_worker() -> None:
    confirm = AsyncMock()
    confirm.system.side_effect = OSError("db down")
    dispatch = AsyncMock()

    await on_successful_payment(_paid_message(), confirm, dispatch)

    dispatch.kiq.assert_awaited_once_with(
        telegram_id=5, payload="ref", currency="XTR", total_amount=50, charge_id="c"
    )


async def test_successful_payment_failure_propagates() -> None:
    confirm = AsyncMock()
    confirm.system.side_effect = OSError("db down")
    dispatch = AsyncMock()
    dispatch.kiq.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await on_successful_payment(_paid_message(), confirm, dispatch)
