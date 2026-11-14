from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Union

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.config.build import BuildConfig
from app.core.constants import GB_TO_BYTES
from app.core.enums import (
    AccessMode,
    Currency,
    Locale,
    PaymentGatewayType,
    PromocodeRewardType,
    SubscriptionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.notifications.dto import NOTIFICATION_GROUPS
from app.modules.notifications.render import NotificationRenderer, notification_args
from app.modules.notifications.telegram_data import CardData
from app.modules.notifications.telegram_layout import LAYOUTS, build_telegram_card
from app.modules.promocodes import PromocodeDto
from app.modules.settings import AccessSettingsDto
from app.modules.subscriptions import PlanSnapshot, SubscriptionDto
from app.modules.transactions import TransactionDto
from app.modules.users import UserDto

_TRANSLATIONS = Path(__file__).parents[3] / "assets" / "translations"
_BUILD = BuildConfig(tag="v0.8.0", time="10.11.2026 18:00", commit="31bdd42abc", branch="remake")
# kept as the sentence: what was done is the whole message
_SENTENCE_ONLY = {"RescueCliUsedEvent"}


class _StrictRenderer(NotificationRenderer):
    """Records every key the card asked for but the translations lack."""

    missing: set[str]

    def text(
        self, locale: Locale, key: str, args: Optional[dict[str, Union[str, int]]] = None
    ) -> Optional[str]:
        value = super().text(locale, key, args)
        if value is None and not key.endswith((".hint", ".emoji")):
            self.missing.add(key)
        return value

    def render_message(self, locale: Locale, key: str, args: dict[str, Union[str, int]]) -> str:
        value = super().render_message(locale, key, args)
        if not value:
            self.missing.add(key)
        return value


def _renderer(locale: Locale) -> _StrictRenderer:
    texts = "\n".join(
        (_TRANSLATIONS / locale.value / name).read_text()
        for name in ("notifications.ftl", "menu.ftl")
    )
    renderer = _StrictRenderer({locale: texts}, default_locale=locale)
    renderer.missing = set()
    return renderer


def _plan(*, is_trial: bool = False) -> PlanSnapshot:
    return PlanSnapshot(
        plan_id=3,
        public_code="std",
        name="Стандарт",
        price_paid=Decimal("299"),
        currency=Currency.RUB,
        duration_days=30,
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        is_trial=is_trial,
    )


def _data() -> CardData:
    subscription = SubscriptionDto.model_construct(
        id=553,
        status=SubscriptionStatus.ACTIVE,
        is_trial=False,
        effective_traffic_limit=100,
        effective_device_limit=3,
        expire_at=datetime_now() + timedelta(days=29, hours=1),
        plan_snapshot=_plan(),
    )
    order = TransactionDto.model_construct(
        id=10293,
        final_price=Decimal("299.00"),
        currency=Currency.RUB,
        gateway_type=PaymentGatewayType.YOOKASSA,
        fulfilled_subscription_id=553,
    )
    user = UserDto.model_construct(
        id=1042, name="Иван Петров", telegram_id=583920117, username="ivan_petrov", email=None
    )
    promocode = PromocodeDto.model_construct(
        code="AUTUMN20", reward_type=PromocodeRewardType.DURATION, reward=7
    )
    return CardData(
        user=user,
        order=order,
        subscription=subscription,
        used_traffic=0,
        promocode=promocode,
        access=AccessSettingsDto(mode=AccessMode.PUBLIC),
    )


_PAYLOAD: dict[str, Any] = {
    "user_id": 1042,
    "session_id": 812,
    "login": "admin",
    "provider": "GITHUB",
    "username": "remnashop_bot",
    "user_agent": "Mozilla/5.0",
    "kind": "DATABASE",
    "run_id": 58,
    "error": "connection refused",
    "subscription_id": 553,
    "days": 7,
    "channel_id": -1001234567890,
    "node_name": "DE-1",
    "message": "timeout",
    "next_billing_at": "15.11.2026",
    "version": "2.1.0",
    "supported": "2.2.0–2.9.x",
    "uptime_seconds": 187200,
    "broadcast_id": 17,
    "sent": 1240,
    "failed": 12,
    "blocked": 37,
    "order_id": 10293,
    "amount": "299.00",
    "currency": "RUB",
    "gateway_type": "YOOKASSA",
    "previous_status": "FAILED",
    "method": "GOOGLE",
    "ad_link_code": "tg_ads_nov",
    "referral_code": "IVAN42",
    "destination": "tracker:6969",
    "hours": 24,
    "hwid": "abc",
    "platform": "iOS",
    "device_model": "iPhone",
    "os_version": "18.1",
    "promocode_id": 1,
    "reward_type": "DURATION",
    "purchase_type": "NEW",
    "is_trial": False,
    "action": "restore_backup",
    "user": {"id": 1042, "name": "Иван", "role": "USER", "telegram_id": 5, "username": "ivan"},
}


def _card(renderer: NotificationRenderer, locale: Locale, event_type: str) -> str:
    args = notification_args(_PAYLOAD, "185.12.44.7")
    title, body = renderer.render(locale, event_type, args)
    return build_telegram_card(
        renderer,
        locale,
        event_type=event_type,
        payload=_PAYLOAD,
        args=args,
        data=_data(),
        build=_BUILD,
        title=title,
        body=body,
        notes="",
    )


def test_every_notified_event_has_a_card_layout() -> None:
    grouped = frozenset().union(*NOTIFICATION_GROUPS.values())
    assert set(LAYOUTS) <= grouped
    assert grouped - set(LAYOUTS) == _SENTENCE_ONLY


@pytest.mark.parametrize("locale", [Locale.RU, Locale.EN])
def test_every_card_label_and_value_is_translated(locale: Locale) -> None:
    renderer = _renderer(locale)
    for event_type in frozenset().union(*NOTIFICATION_GROUPS.values()):
        _card(renderer, locale, event_type)
    assert renderer.missing == set()


def test_purchase_card_shows_payment_subscription_plan_and_user() -> None:
    card = _card(_renderer(Locale.RU), Locale.RU, "SubscriptionPurchasedEvent")

    assert card == (
        "#SubscriptionPurchasedEvent\n\n"
        "<b>🔅 Событие: Покупка подписки!</b>\n\n"
        "👤 <b>Пользователь</b>:\n<blockquote>• <b>ID</b>: <code>1042</code>\n"
        "• <b>Имя</b>: Иван\n• <b>Telegram ID</b>: <code>5</code>\n"
        "• <b>Username</b>: @ivan</blockquote>\n\n"
        "💰 <b>Платёж</b>:\n<blockquote>• <b>ID</b>: <code>10293</code>\n"
        "• <b>Способ оплаты</b>: YooKassa\n• <b>Сумма</b>: 299\xa0₽</blockquote>\n\n"
        "💳 <b>Подписка</b>:\n<blockquote>• <b>ID</b>: <code>553</code>\n"
        "• <b>Статус</b>: Активна\n• <b>Трафик</b>: 0 МБ / 100 ГБ\n"
        "• <b>Лимит устройств</b>: 3\n• <b>Осталось</b>: 30 дней</blockquote>\n\n"
        "📦 <b>План</b>:\n<blockquote>• <b>План</b>: <code>Стандарт</code>\n"
        "• <b>Тип</b>: Трафик + устройства\n• <b>Лимит трафика</b>: 100 ГБ\n"
        "• <b>Лимит устройств</b>: 3\n• <b>Длительность</b>: 30 дней</blockquote>"
    )


def test_an_unlimited_purchase_card_says_no_end_date() -> None:
    renderer = _renderer(Locale.RU)
    data = _data()
    assert data.subscription is not None
    subscription = data.subscription.model_copy(
        update={
            "expire_at": datetime_now().replace(year=2099),
            "plan_snapshot": replace(_plan(), duration_days=0),
        }
    )
    args = notification_args(_PAYLOAD, "185.12.44.7")
    title, body = renderer.render(Locale.RU, "SubscriptionPurchasedEvent", args)

    card = build_telegram_card(
        renderer,
        Locale.RU,
        event_type="SubscriptionPurchasedEvent",
        payload=_PAYLOAD,
        args=args,
        data=replace(data, subscription=subscription),
        build=_BUILD,
        title=title,
        body=body,
        notes="",
    )

    assert "• <b>Осталось</b>: бессрочно" in card
    assert "• <b>Длительность</b>: бессрочно" in card
    assert not renderer.missing


def test_a_plan_change_shows_old_and_new_plan_side_by_side() -> None:
    renderer = _renderer(Locale.RU)
    previous = {"name": "Базовый", "traffic_limit": 0, "device_limit": 3, "duration_days": 30}
    payload = {**_PAYLOAD, "previous_plan_snapshot": previous}
    args = notification_args(payload, None)
    title, body = renderer.render(Locale.RU, "SubscriptionChangedEvent", args)

    card = build_telegram_card(
        renderer,
        Locale.RU,
        event_type="SubscriptionChangedEvent",
        payload=payload,
        args=args,
        data=_data(),
        build=_BUILD,
        title=title,
        body=body,
        notes="",
    )

    assert "ℹ️" not in card
    assert card.endswith(
        "📦 <b>План</b>:\n<blockquote>• <b>План</b>: <code>Базовый → Стандарт</code>\n"
        "• <b>Тип</b>: Устройства → Трафик + устройства\n"
        "• <b>Лимит трафика</b>: Безлимит → 100 ГБ\n"
        "• <b>Лимит устройств</b>: 3\n"
        "• <b>Длительность</b>: 30 дней</blockquote>"
    )


def test_merged_events_share_a_hashtag_and_the_difference_is_a_row() -> None:
    renderer = _renderer(Locale.RU)
    password = _card(renderer, Locale.RU, "LoginFailedEvent")
    passkey = _card(renderer, Locale.RU, "PasskeyLoginFailedEvent")

    assert password.startswith("#LoginFailedEvent\n\n<b>⚠️ Событие: Неудачная попытка входа!</b>")
    assert passkey.startswith("#LoginFailedEvent\n\n<b>⚠️ Событие: Неудачная попытка входа!</b>")
    assert "• <b>Способ</b>: Passkey" in passkey


def test_a_bare_user_id_becomes_the_user_block_without_empty_rows() -> None:
    card = _card(_renderer(Locale.RU), Locale.RU, "PaidOrderNotFulfilledEvent")

    assert "👤 <b>Пользователь</b>:\n<blockquote>• <b>ID</b>: <code>1042</code>" in card
    assert "Почта" not in card


@pytest.mark.parametrize(
    "event_type", ["BotStartedEvent", "PanelLoginFailedEvent", "SessionTheftDetectedEvent"]
)
def test_a_system_event_has_no_user_block(event_type: str) -> None:
    renderer = _renderer(Locale.RU)
    payload = {k: v for k, v in _PAYLOAD.items() if k != "user"}
    args = notification_args(payload, None)
    title, body = renderer.render(Locale.RU, event_type, args)

    card = build_telegram_card(
        renderer,
        Locale.RU,
        event_type=event_type,
        payload=payload,
        args=args,
        data=_data(),
        build=_BUILD,
        title=title,
        body=body,
        notes="",
    )

    assert "👤" not in card


def test_the_hint_closes_the_card_in_a_quote() -> None:
    card = _card(_renderer(Locale.RU), Locale.RU, "RequiredChannelCheckFailedEvent")

    assert card.endswith(
        "\n\n<blockquote>Пока проблема не решена, клиенты проходят без проверки.</blockquote>"
    )


@pytest.mark.parametrize(
    ("size", "shown"),
    [
        (0, "0 МБ"),
        (300 * 1024**2, "300 МБ"),
        (GB_TO_BYTES * 3 // 2, "1,5 ГБ"),
        (GB_TO_BYTES, "1 ГБ"),
    ],
)
def test_traffic_starts_at_megabytes(size: int, shown: str) -> None:
    data = _data()
    data = CardData(
        user=data.user,
        order=data.order,
        subscription=data.subscription,
        used_traffic=size,
        promocode=data.promocode,
        access=data.access,
    )
    renderer = _renderer(Locale.RU)
    args = notification_args(_PAYLOAD, None)
    title, body = renderer.render(Locale.RU, "SubscriptionExpiredEvent", args)
    card = build_telegram_card(
        renderer,
        Locale.RU,
        event_type="SubscriptionExpiredEvent",
        payload=_PAYLOAD,
        args=args,
        data=data,
        build=_BUILD,
        title=title,
        body=body,
        notes="",
    )
    assert f"• <b>Трафик</b>: {shown} / 100 ГБ" in card
