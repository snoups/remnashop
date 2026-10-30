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
    "SubscriptionPurchasedEvent": {},
    "SubscriptionRenewedEvent": {"duration_days": 1},
    "SubscriptionChangedEvent": {},
    "SubscriptionAddOnGrantedEvent": {"addon_type": "TRAFFIC", "amount": 10},
    "SubscriptionGrantedEvent": {"duration_days": 30},
    "TransactionRefundedEvent": {"order_id": 1, "amount": "1500.00", "currency": "RUB"},
    "TransactionPartiallyRefundedEvent": {"order_id": 1, "amount": "12.5", "currency": "USD"},
    "PaidOrderNotFulfilledEvent": {"order_id": 1, "amount": "10.00", "currency": "USD"},
    "SubscriptionExpiringEvent": {"hours": 24, "is_trial": "no"},
    "SubscriptionExpiredEvent": {"is_trial": "yes"},
    "SubscriptionExpiredAgoEvent": {"hours": 72, "is_trial": "no"},
    "SubscriptionTrafficLimitedEvent": {"is_trial": "no"},
    "SubscriptionTrafficThresholdEvent": {"is_trial": "yes"},
    "SubscriptionNotConnectedEvent": {"hours": 5},
    "CabinetNewDeviceSignInEvent": {"ip": "1.2.3.4", "browser": "Firefox"},
    "PromocodeDiscountExpiringEvent": {"percent": 10, "code": "SALE", "hours": 1},
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
            "Подписка закончится через 23 ч. Продлите её, чтобы не потерять доступ.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiringEvent",
            {"hours": 24, "is_trial": "yes"},
            "Подписка закончится через 1 день. Оформите подписку, чтобы не потерять доступ.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiredAgoEvent",
            {"hours": 48, "is_trial": "no"},
            "Подписка закончилась 2 дня назад. Продлите её, чтобы вернуть доступ.",
        ),
        (
            Locale.RU,
            "SubscriptionNotConnectedEvent",
            {"hours": 120},
            "Вы оформили подписку 5 дней назад, но ещё не подключились. "
            "Подключите устройство, это займёт пару минут.",
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
            "Платёж на 1\xa0500\xa0₽ возвращён.",
        ),
        (
            Locale.RU,
            "PromocodeDiscountExpiringEvent",
            {"percent": 10, "code": "SALE", "hours": 72},
            "Скидка 10% по промокоду SALE действует ещё 3 дня. Успейте оформить покупку.",
        ),
        (
            Locale.EN,
            "SubscriptionTrafficThresholdEvent",
            {"is_trial": "yes"},
            "Your traffic is running low. Get a subscription to keep your access.",
        ),
        (
            Locale.EN,
            "SubscriptionExpiringEvent",
            {"hours": 1, "is_trial": "no"},
            "Your subscription ends in 1 h. Renew it to keep your access.",
        ),
        (
            Locale.EN,
            "SubscriptionRenewedEvent",
            {"duration_days": 1},
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
            "$12.50 of your payment was refunded.",
        ),
        (
            Locale.EN,
            "PromocodeDiscountExpiringEvent",
            {"percent": 10, "code": "SALE", "hours": 1},
            "Your 10% discount from promocode SALE is valid for 1 more hour. "
            "Make your purchase before it’s gone.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiredEvent",
            {"is_trial": "yes"},
            "Подписка закончилась. Оформите подписку, чтобы вернуть доступ.",
        ),
        (
            Locale.RU,
            "SubscriptionExpiredAgoEvent",
            {"hours": 48, "is_trial": "yes"},
            "Подписка закончилась 2 дня назад. Оформите подписку, чтобы вернуть доступ.",
        ),
        (
            Locale.RU,
            "SubscriptionTrafficLimitedEvent",
            {"is_trial": "yes"},
            "Лимит трафика исчерпан. Оформите подписку, чтобы вернуть доступ.",
        ),
        (
            Locale.EN,
            "SubscriptionExpiredEvent",
            {"is_trial": "yes"},
            "Your subscription has expired. Get a subscription to get your access back.",
        ),
        (
            Locale.EN,
            "SubscriptionExpiredAgoEvent",
            {"hours": 48, "is_trial": "yes"},
            "Your subscription expired 2 days ago. Get a subscription to get your access back.",
        ),
        (
            Locale.EN,
            "SubscriptionTrafficLimitedEvent",
            {"is_trial": "yes"},
            "Your traffic limit is reached. Get a subscription to get your access back.",
        ),
    ],
)
def test_template_text(
    locale: Locale, event_type: str, args: dict[str, Union[str, int]], body: str
) -> None:
    assert _render(locale, event_type, args) == body
