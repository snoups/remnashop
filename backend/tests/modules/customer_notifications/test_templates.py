from pathlib import Path
from typing import Union

import pytest
from fluent.syntax import FluentParser
from fluent.syntax.ast import Message
from fluent_compiler.bundle import FluentBundle

from app.core.enums import Locale
from app.core.event_bus import EventBus
from app.modules.customer_notifications.render_args import customer_render_args
from app.modules.customer_notifications.subscribers import register_subscribers
from app.modules.notifications.render import message_id
from app.modules.transactions import TransactionCanceledEvent, TransactionExpiredEvent

_TRANSLATIONS_DIR = Path(__file__).parents[3] / "assets" / "translations"
# shown only as a bot window, never as a text
_WINDOW_ONLY = {TransactionCanceledEvent.__name__, TransactionExpiredEvent.__name__}


@pytest.mark.parametrize("locale", (Locale.EN, Locale.RU))
def test_every_customer_event_has_a_template(locale: Locale) -> None:
    resource = FluentParser().parse(
        (_TRANSLATIONS_DIR / locale.value / "notifications.ftl").read_text()
    )
    ids = {e.id.name for e in resource.body if isinstance(e, Message)}
    bus = EventBus()
    register_subscribers(bus)
    for event_type in bus._handlers.keys() - _WINDOW_ONLY:
        key = message_id(f"Customer{event_type}")
        assert key in ids, f"{key} missing in {locale}"


_ARGS: dict[str, dict[str, Union[str, int]]] = {
    "SubscriptionPurchasedEvent": {"paid": "yes", "is_trial": "no"},
    "SubscriptionRenewedEvent": {"duration_days": 1, "paid": "yes"},
    "SubscriptionChangedEvent": {"paid": "no"},
    "SubscriptionAddOnGrantedEvent": {"addon_type": "TRAFFIC", "amount": 10},
    "SubscriptionGrantedEvent": {"duration_days": 30},
    "TransactionRefundedEvent": {"order_id": 1, "amount": "1500.00", "currency": "RUB"},
    "TransactionPartiallyRefundedEvent": {"order_id": 1, "amount": "12.5", "currency": "USD"},
    "PaidOrderNotFulfilledEvent": {"order_id": 1, "amount": "10.00", "currency": "USD"},
    "SubscriptionExpiringEvent": {"hours": 24, "is_trial": "no"},
    "SubscriptionExpiredEvent": {"is_trial": "yes"},
    "SubscriptionExpiredAgoEvent": {"hours": 72, "is_trial": "no"},
    "SubscriptionTrafficLimitedEvent": {"is_trial": "no", "traffic_strategy": "MONTH"},
    "SubscriptionTrafficThresholdEvent": {"is_trial": "yes"},
    "SubscriptionNotConnectedEvent": {"hours": 5},
    "CabinetNewDeviceSignInEvent": {"ip": "1.2.3.4", "browser": "Firefox"},
    "PromocodeDiscountExpiringEvent": {"percent": 10, "code": "SALE", "hours": 1},
    "PaymentsRestored": {},
    "TorrentBlockerReportEvent": {"block_unit": "minute", "block_span": 30},
    "ReferralRewardIssuedEvent": {
        "reward_type": "EXTRA_DAYS",
        "amount": 7,
        "name": "Иван",
        "has_name": "yes",
    },
    "ReferralAttachedEvent": {"name": "Иван", "rewarded": "yes"},
}


def _bundle(locale: Locale) -> FluentBundle:
    text = (_TRANSLATIONS_DIR / locale.value / "notifications.ftl").read_text()
    return FluentBundle.from_string(locale.value, text, use_isolating=False)  # type: ignore[no-untyped-call]


def _render(locale: Locale, event_type: str, args: dict[str, Union[str, int]]) -> str:
    body, errors = _bundle(locale).format(
        message_id(f"Customer{event_type}"), customer_render_args(args, locale)
    )
    assert errors == [], (locale, event_type, errors)
    return str(body)


@pytest.mark.parametrize("locale", (Locale.EN, Locale.RU))
@pytest.mark.parametrize("event_type", _ARGS)
def test_changed_template_renders(locale: Locale, event_type: str) -> None:
    body = _render(locale, event_type, _ARGS[event_type])

    assert body and "{" not in body


@pytest.mark.parametrize(
    ("locale", "event_type", "args", "body"),
    [
        (
            Locale.RU,
            "SubscriptionExpiringEvent",
            {"hours": 23, "is_trial": "no"},
            "Ваша подписка закончится через 23 ч. "
            "Продлите её заранее, чтобы не терять доступ к сервису.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiringEvent",
            {"hours": 24, "is_trial": "yes"},
            "Ваш пробный период закончится через 1 день. "
            "Оформите подписку, чтобы не терять доступ к сервису.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiredAgoEvent",
            {"hours": 48, "is_trial": "no"},
            "Ваша подписка истекла 2 дня назад. Продлите её, чтобы снова пользоваться VPN.",
        ),
        (
            Locale.RU,
            "SubscriptionNotConnectedEvent",
            {"hours": 120},
            "Вы оформили подписку 5 дней назад, но ещё ни разу ею не воспользовались. "
            "Если с настройкой возникли сложности, напишите в поддержку — разберёмся вместе.",
        ),
        (
            Locale.RU,
            "SubscriptionAddOnGrantedEvent",
            {"addon_type": "DEVICES", "amount": 2},
            "К подписке добавлено 2 устройства.",
        ),
        (
            Locale.RU,
            "SubscriptionAddOnGrantedEvent",
            {"addon_type": "TRAFFIC", "amount": 50},
            "К подписке добавлено 50 ГБ трафика.",
        ),
        (
            Locale.RU,
            "TransactionRefundedEvent",
            {"order_id": 1, "amount": "1500.00", "currency": "RUB"},
            "1\xa0500\xa0₽ вернутся тем же способом, которым вы платили.",
        ),
        (
            Locale.RU,
            "PromocodeDiscountExpiringEvent",
            {"percent": 10, "code": "SALE", "hours": 72},
            "10% по промокоду SALE действуют ещё 3 дня. Успейте оформить покупку.",
        ),
        (
            Locale.EN,
            "SubscriptionTrafficThresholdEvent",
            {"is_trial": "yes"},
            "Get a subscription to keep your access.",
        ),
        (
            Locale.EN,
            "SubscriptionExpiringEvent",
            {"hours": 1, "is_trial": "no"},
            "Your subscription ends in 1 h. Renew it in advance to keep your access.",
        ),
        (
            Locale.EN,
            "SubscriptionRenewedEvent",
            {"duration_days": 1, "paid": "yes"},
            "Your subscription was extended by 1 day.",
        ),
        (
            Locale.EN,
            "SubscriptionAddOnGrantedEvent",
            {"addon_type": "DEVICES", "amount": 1},
            "1 device added to your subscription.",
        ),
        (
            Locale.EN,
            "TransactionPartiallyRefundedEvent",
            {"order_id": 1, "amount": "12.5", "currency": "USD"},
            "Part of your payment, $12.50, will go back the way you paid.",
        ),
        (
            Locale.EN,
            "PromocodeDiscountExpiringEvent",
            {"percent": 10, "code": "SALE", "hours": 1},
            "Your 10% off with promocode SALE is valid for 1 more hour. "
            "Make your purchase before it’s gone.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiredEvent",
            {"is_trial": "yes"},
            "Ваш пробный период закончился. Оформите подписку, чтобы продолжить пользоваться VPN.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiredAgoEvent",
            {"hours": 48, "is_trial": "yes"},
            "Ваш пробный период закончился 2 дня назад. "
            "Оформите подписку, чтобы снова пользоваться VPN.",
        ),
        (
            Locale.RU,
            "SubscriptionTrafficLimitedEvent",
            {"is_trial": "yes"},
            "Ваш трафик израсходован. Оформите подписку, чтобы продолжить пользоваться сервисом.",
        ),
        (
            Locale.RU,
            "SubscriptionTrafficLimitedEvent",
            {"is_trial": "no", "traffic_strategy": "NO_RESET"},
            "Ваш трафик израсходован. "
            "Продлите подписку, чтобы сбросить трафик и продолжить пользоваться сервисом.",
        ),
        (
            Locale.RU,
            "SubscriptionTrafficLimitedEvent",
            {"is_trial": "no", "traffic_strategy": "DAY"},
            "Ваш трафик израсходован. "
            "Он восстановится завтра, или продлите подписку, чтобы сбросить его сейчас.",
        ),
        (
            Locale.RU,
            "TorrentBlockerReportEvent",
            {"block_unit": "minute", "block_span": 30},
            "Мы заметили торрент-трафик через VPN. Торренты запрещены правилами сервиса, "
            "поэтому подключение ограничено на 30 минут. Отключите торрент-клиент или исключите "
            "его из VPN, чтобы это не повторялось. При повторных нарушениях доступ может быть "
            "ограничен надолго.",
        ),
        (
            Locale.RU,
            "ReferralRewardIssuedEvent",
            {"reward_type": "EXTRA_DAYS", "amount": 7, "name": "Иван", "has_name": "yes"},
            "Пользователь Иван совершил платёж — вам начислено 7 бонусных дней. "
            "Спасибо, что пригласили!",
        ),
        (
            Locale.RU,
            "ReferralRewardIssuedEvent",
            {"reward_type": "POINTS", "amount": 2, "name": "", "has_name": "no"},
            "вам начислено 2 балла. Спасибо, что пригласили!",
        ),
        (
            Locale.RU,
            "ReferralAttachedEvent",
            {"name": "Иван", "rewarded": "no"},
            "Пользователь Иван присоединился по вашей пригласительной ссылке.",
        ),
        (
            Locale.EN,
            "SubscriptionExpiredEvent",
            {"is_trial": "yes"},
            "Your trial has ended. Get a subscription to keep using the VPN.",
        ),
        (
            Locale.EN,
            "SubscriptionExpiredAgoEvent",
            {"hours": 48, "is_trial": "yes"},
            "Your trial ended 2 days ago. Get a subscription to use the VPN again.",
        ),
        (
            Locale.EN,
            "SubscriptionTrafficLimitedEvent",
            {"is_trial": "yes"},
            "You've used up your traffic. Get a subscription to keep using the service.",
        ),
    ],
)
def test_template_text(
    locale: Locale, event_type: str, args: dict[str, Union[str, int]], body: str
) -> None:
    assert _render(locale, event_type, args) == body
