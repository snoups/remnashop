from decimal import Decimal
from hashlib import sha256
from typing import Final, Optional

from pydantic import BaseModel

from app.core.config import AppConfig
from app.core.enums import Currency, Locale, PurchaseType
from app.modules.transactions.recurring_policy import RETRY_OFFSETS_HOURS

TERMS_VERSION: Final[str] = "2"


class RecurringTerms(BaseModel):
    version: str
    terms_id: str
    user_id: int
    plan_id: int
    target_subscription_id: Optional[int]
    purchase_type: PurchaseType
    initial_amount: Decimal
    amount_limit: Decimal
    currency: Currency
    duration_days: int
    lead_minutes: int
    retry_minutes: int
    # Missing on older accepted revisions: never widen their retry authorization implicitly.
    retry_offsets_hours: tuple[int, ...] = ()
    pending_timeout_hours: int = 24
    max_overdue_hours: int
    locale: Locale
    summary: str
    text: str

    def covers(
        self,
        config: AppConfig,
        *,
        user_id: int,
        plan_id: int,
        amount: Decimal,
        duration_days: int,
        currency: Currency,
    ) -> bool:
        return (
            self.user_id == user_id
            and self.plan_id == plan_id
            and self.currency is currency
            and self.duration_days == duration_days
            and 0 < amount <= self.amount_limit
        )


def build_recurring_terms(
    *,
    config: AppConfig,
    user_id: int,
    plan_id: int,
    target_subscription_id: Optional[int],
    purchase_type: PurchaseType,
    initial_amount: Decimal,
    amount_limit: Decimal,
    currency: Currency,
    duration_days: int,
    locale: Locale,
) -> RecurringTerms:
    policy = config.recurring
    amount = format(amount_limit.normalize(), "f")
    initial = format(initial_amount.normalize(), "f")
    retry_hours = ", ".join(str(hour) for hour in RETRY_OFFSETS_HOURS)
    if locale.value == "ru":
        summary = (
            "По вашему согласию — сохранение способа оплаты в ЮKassa и автоматические "
            f"списания до {amount} {currency.symbol} за каждые "
            f"{duration_days} дней, начиная за {policy.lead_minutes} мин. до окончания подписки. "
            "Отключить будущие списания можно в настройках подписки в боте или личном кабинете."
        )
        text = (
            "Условия автоматического продления\n\n"
            f"Текущая оплата: {initial} {currency.symbol}.\n"
            f"Продление: не более {amount} {currency.symbol} за каждые {duration_days} дней. "
            "Разовая скидка на будущие продления не распространяется. Если стоимость "
            "превысит указанный предел или изменятся условия тарифа, автосписания остановятся.\n\n"
            f"Попытка оплаты начинается за {policy.lead_minutes} мин. до окончания "
            "оплаченного периода. После отказа банка возможны повторные списания через "
            f"{retry_hours} ч. от первого отказа, в пределах указанного окна. "
            "При временном сбое запрос может повторяться с интервалом "
            f"{policy.retry_minutes} мин., но новые попытки не начинаются позднее "
            f"{policy.max_overdue_hours} ч. после окончания подписки. "
            "Уже отправленный платёж может завершиться позже.\n\n"
            "Давая согласие, вы разрешаете сохранить способ оплаты через ЮKassa и "
            "использовать его для автоматической оплаты этой подписки без отдельного "
            "подтверждения каждого списания.\n\n"
            "Отозвать согласие и запретить дальнейшие списания можно кнопкой "
            "«Отключить автопродление» в настройках подписки в боте или личном кабинете. "
            "Отказ прекращает новые попытки списания; уже отправленный платёж может "
            "завершиться. Оплаченный срок сохраняется. Повторное подключение требует "
            "нового явного согласия."
        )
    else:
        summary = (
            "With your consent, auto-renewal saves your payment method with YooKassa "
            "and authorizes "
            f"automatic charges up to {amount} {currency.value} every {duration_days} days, "
            f"starting {policy.lead_minutes} min. before expiry. Stop future charges "
            "in your subscription settings in the bot or customer account."
        )
        text = (
            "Automatic renewal terms\n\n"
            f"Current payment: {initial} {currency.value}.\n"
            f"Renewals: up to {amount} {currency.value} every {duration_days} days. "
            "One-time discounts do not apply to renewals. Charges stop if the price exceeds "
            "this limit or the plan terms change.\n\n"
            f"Payment starts {policy.lead_minutes} min. before the paid period expires. "
            f"A bank decline may be retried at {retry_hours} hours from the first failure, "
            "within the agreed window. "
            f"A temporary failure may be retried every {policy.retry_minutes} min.; "
            f"new attempts stop {policy.max_overdue_hours} hours after expiry. "
            "A payment already submitted may complete later.\n\n"
            "By consenting, you authorize saving your payment method through YooKassa "
            "and using it to renew this subscription without confirming each charge.\n\n"
            "Withdraw consent and stop future charges with Disable auto-renewal in your "
            "subscription settings in the bot or customer account. Withdrawal stops new "
            "attempts; a payment already submitted may complete. Your paid period remains "
            "available. Reconnection requires fresh explicit consent."
        )
    terms = RecurringTerms(
        version=TERMS_VERSION,
        terms_id="",
        user_id=user_id,
        plan_id=plan_id,
        target_subscription_id=target_subscription_id,
        purchase_type=purchase_type,
        initial_amount=Decimal(format(initial_amount.normalize(), "f")),
        amount_limit=Decimal(format(amount_limit.normalize(), "f")),
        currency=currency,
        duration_days=duration_days,
        lead_minutes=policy.lead_minutes,
        retry_minutes=policy.retry_minutes,
        max_overdue_hours=policy.max_overdue_hours,
        retry_offsets_hours=RETRY_OFFSETS_HOURS,
        pending_timeout_hours=policy.pending_timeout_hours,
        locale=locale,
        summary=summary,
        text=text,
    )
    # The fingerprint binds the displayed terms to this customer, selection and policy.
    return terms.model_copy(
        update={"terms_id": sha256(terms.model_dump_json().encode()).hexdigest()}
    )
