from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from dishka import FromDishka
from fluentogram import TranslatorHub
from loguru import logger

from app.modules.transactions import (
    ConfirmStarsPaymentDispatch,
    ConfirmStarsPaymentUseCase,
    StarsPaymentDto,
    StarsPreCheckoutDto,
    ValidateStarsPreCheckoutUseCase,
)

router = Router(name=__name__)


@router.pre_checkout_query()
async def on_pre_checkout(
    query: PreCheckoutQuery,
    validate: FromDishka[ValidateStarsPreCheckoutUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    ok = await validate.system(
        StarsPreCheckoutDto(
            telegram_id=query.from_user.id,
            payload=query.invoice_payload,
            currency=query.currency,
            total_amount=query.total_amount,
        )
    )
    if ok:
        await query.answer(ok=True)
        return
    # no UserDto at pre-checkout; "pt-br" -> "pt", unserved codes fall back to the root locale
    code = (query.from_user.language_code or "").split("-")[0].lower()
    locale = code if code in i18n.translators_map else i18n.root_locale
    runner = i18n.get_translator_by_locale(locale)
    await query.answer(ok=False, error_message=runner.get("ntf-purchase.stars-rejected"))


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message,
    confirm: FromDishka[ConfirmStarsPaymentUseCase],
    dispatch: FromDishka[ConfirmStarsPaymentDispatch],
) -> None:
    payment = message.successful_payment
    if payment is None or message.from_user is None:
        return
    data = StarsPaymentDto(
        telegram_id=message.from_user.id,
        payload=payment.invoice_payload,
        currency=payment.currency,
        total_amount=payment.total_amount,
        charge_id=payment.telegram_payment_charge_id,
    )
    # settled here, not just queued: a queued message dies with Redis, while a
    # PAID order is picked up by the reconciliation sweep
    try:
        await confirm.system(data)
        return
    except Exception:
        logger.exception(
            f"Stars payment '{data.charge_id}' not settled in place; queueing it for the worker"
        )
    # the webhook is already answered, so a failure here is never redelivered by Telegram
    try:
        await dispatch.kiq(
            telegram_id=data.telegram_id,
            payload=data.payload,
            currency=data.currency,
            total_amount=data.total_amount,
            charge_id=data.charge_id,
        )
    except Exception:
        logger.exception(
            f"Stars payment '{data.charge_id}' for payload '{data.payload}' failed to "
            "queue -- check and refund manually"
        )
        raise
