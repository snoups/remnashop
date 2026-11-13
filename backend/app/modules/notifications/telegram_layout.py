import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Optional, Union

from babel.numbers import format_decimal

from app.core.config.build import BuildConfig
from app.core.constants import GB_TO_BYTES
from app.core.enums import Locale, PromocodeRewardType, Role
from app.core.utils.money import format_money
from app.core.utils.time import datetime_now
from app.modules.notifications.render import (
    CardBlock,
    CardRow,
    NotificationRenderer,
    message_id,
    telegram_card,
)
from app.modules.notifications.telegram_data import CardData, CardSection
from app.modules.subscriptions import SubscriptionDto

_MB: Final[int] = 1024**2
_DEFAULT_EMOJI: Final[str] = "🔅"
_COMMIT_LENGTH: Final[int] = 7


class _Card:
    """One admin's view of one event: labels and values in their locale."""

    def __init__(
        self,
        renderer: NotificationRenderer,
        locale: Locale,
        event_type: str,
        payload: dict[str, Any],
        args: dict[str, Union[str, int]],
        data: CardData,
        build: Optional[BuildConfig],
    ) -> None:
        self.renderer = renderer
        self.locale = locale
        self.event_type = event_type
        self.payload = payload
        self.args = args
        self.data = data
        self.build = build

    def label(self, key: str) -> str:
        return self.renderer.text(self.locale, f"ntf-telegram-label.{key}") or key

    def value(self, kind: str, value: object) -> str:
        if value is None or value == "":
            return ""
        args: dict[str, Union[str, int]] = {"value": str(value)}
        return self.renderer.render_message(self.locale, f"ntf-telegram-{kind}", args)

    def arg(self, name: str) -> str:
        value = self.args.get(name)
        return "" if value is None else str(value)

    def days(self, count: Optional[int]) -> str:
        if count is None:
            return ""
        return self.renderer.render_message(self.locale, "ntf-telegram-days", {"count": count})

    def traffic(self, size: int) -> str:
        # the smallest unit is a megabyte: "0 MB", never bytes
        for unit, scale in (("TB", GB_TO_BYTES * 1024), ("GB", GB_TO_BYTES)):
            if size >= scale:
                return self._traffic(unit, size / scale)
        return self._traffic("MB", round(size / _MB))

    def _traffic(self, unit: str, amount: float) -> str:
        shown = format_decimal(amount, format="#,##0.#", locale=self.locale.value)
        return self.renderer.render_message(
            self.locale, "ntf-telegram-traffic", {"unit": unit, "amount": shown}
        )

    def traffic_limit(self, gigabytes: int) -> str:
        return self.label("unlimited") if gigabytes == 0 else self.traffic(gigabytes * GB_TO_BYTES)

    def count_limit(self, count: int) -> str:
        return self.label("unlimited") if count == 0 else str(count)

    def gateway(self, gateway_type: object) -> str:
        if not gateway_type:
            return ""
        return self.renderer.text(self.locale, f"gateway-name.{gateway_type}") or str(gateway_type)

    def money(self, amount: object, currency: object) -> str:
        if amount is None or currency is None:
            return ""
        return format_money(str(amount), str(currency), self.locale)


Value = Callable[[_Card], str]
# (label key, value, monospace)
Detail = tuple[str, Value, bool]


def _arg(name: str) -> Value:
    return lambda card: card.arg(name)


def _mention(name: str) -> Value:
    return lambda card: f"@{card.arg(name)}" if card.arg(name) else ""


def _const(label_key: str) -> Value:
    return lambda card: card.label(label_key)


def _enum(kind: str, name: str) -> Value:
    return lambda card: card.value(kind, card.args.get(name))


def _uptime(card: _Card) -> str:
    seconds = card.payload.get("uptime_seconds")
    if not isinstance(seconds, int):
        return ""
    days, rest = divmod(seconds, 86400)
    args: dict[str, Union[str, int]] = {
        "days": days,
        "hours": rest // 3600,
        "minutes": rest % 3600 // 60,
    }
    return card.renderer.render_message(card.locale, "ntf-telegram-uptime", args)


@dataclass(frozen=True, kw_only=True)
class CardLayout:
    details: tuple[Detail, ...] = ()
    sections: frozenset[CardSection] = frozenset()
    # one hashtag for events an admin reads as the same thing
    hashtag: Optional[str] = None
    # the payload carries a bare user_id, not the user's snapshot
    load_user: bool = False


_IP: Final[Detail] = ("ip", _arg("ip"), True)
_ERROR: Final[Detail] = ("error", _arg("error"), False)
_NODE: Final[Detail] = ("node", _arg("node_name"), False)
_USER_ID: Final[Detail] = ("user", _arg("user_id"), True)
_BROADCAST: Final[Detail] = ("broadcast", _arg("broadcast_id"), True)
_PANEL_LOGIN: Final[tuple[Detail, ...]] = (
    ("login", _arg("username"), True),
    _IP,
    ("user-agent", _arg("user_agent"), False),
)
_AD_LINK: Final[Detail] = ("ad-link", _arg("ad_link_code"), True)
_REFERRAL_CODE: Final[Detail] = ("referral-code", _arg("referral_code"), True)
_SUBSCRIPTION: Final[frozenset[CardSection]] = frozenset(
    {CardSection.SUBSCRIPTION, CardSection.PLAN}
)
_PURCHASE: Final[frozenset[CardSection]] = _SUBSCRIPTION | {CardSection.PAYMENT}
_PAYMENT: Final[frozenset[CardSection]] = frozenset({CardSection.PAYMENT})

# an event without a layout keeps its sentence as the card's text
LAYOUTS: Final[dict[str, CardLayout]] = {
    "SessionTheftDetectedEvent": CardLayout(
        details=(_USER_ID, ("session", _arg("session_id"), True), _IP)
    ),
    "LoginFailedEvent": CardLayout(
        details=(
            ("method", _const("method-password"), False),
            ("login", _arg("login"), True),
            _IP,
        ),
        hashtag="LoginFailedEvent",
    ),
    "PasskeyLoginFailedEvent": CardLayout(
        details=(("method", _const("method-passkey"), False), _IP),
        hashtag="LoginFailedEvent",
    ),
    "OAuthLoginFailedEvent": CardLayout(
        details=(
            ("method", _const("method-oauth"), False),
            ("provider", _enum("oauth-provider", "provider"), False),
            _IP,
        ),
        hashtag="LoginFailedEvent",
    ),
    "PanelLoginFailedEvent": CardLayout(details=_PANEL_LOGIN),
    "PanelLoginSucceededEvent": CardLayout(details=_PANEL_LOGIN),
    "BackupFailedEvent": CardLayout(
        details=(
            ("kind", _enum("backup-kind", "kind"), False),
            ("run", _arg("run_id"), True),
            _ERROR,
        )
    ),
    "BonusDaysRenewalStuckEvent": CardLayout(
        details=(
            ("subscription", _arg("subscription_id"), True),
            ("bonus-days", _arg("days"), False),
            _ERROR,
        ),
        load_user=True,
    ),
    "RequiredChannelCheckFailedEvent": CardLayout(
        details=(("channel", _arg("channel_id"), True), _ERROR)
    ),
    "TelegramWebhookFailedEvent": CardLayout(details=(_ERROR,)),
    "NodeConnectionLostEvent": CardLayout(details=(_NODE, ("reason", _arg("message"), False))),
    "NodeConnectionRestoredEvent": CardLayout(details=(_NODE,)),
    "NodeTrafficReachedEvent": CardLayout(details=(_NODE,)),
    "NodeBillingDueEvent": CardLayout(
        details=(
            _NODE,
            ("provider", _arg("provider"), False),
            ("billing-date", _arg("next_billing_at"), False),
        )
    ),
    "RemnawaveUnavailableEvent": CardLayout(details=(_ERROR,)),
    "RemnawaveRestoredEvent": CardLayout(),
    "SystemHealthDegradedEvent": CardLayout(),
    "SystemHealthRestoredEvent": CardLayout(),
    "RemnawaveVersionMismatchEvent": CardLayout(
        details=(("version", _arg("version"), True), ("supported", _arg("supported"), True))
    ),
    "PanelStartedEvent": CardLayout(),
    "BotStartedEvent": CardLayout(
        details=(("bot", _mention("username"), False),),
        sections=frozenset({CardSection.BUILD, CardSection.ACCESS}),
    ),
    "BotStoppedEvent": CardLayout(
        details=(("uptime", _uptime, False),), sections=frozenset({CardSection.BUILD})
    ),
    "BroadcastCompletedEvent": CardLayout(
        details=(
            _BROADCAST,
            ("sent", _arg("sent"), False),
            ("failed", _arg("failed"), False),
            ("blocked", _arg("blocked"), False),
        )
    ),
    "BroadcastFailedEvent": CardLayout(details=(_BROADCAST, _ERROR)),
    "SubscriptionPurchasedEvent": CardLayout(sections=_PURCHASE),
    "SubscriptionRenewedEvent": CardLayout(sections=_PURCHASE),
    "SubscriptionChangedEvent": CardLayout(sections=_PURCHASE),
    "TransactionRefundedEvent": CardLayout(
        sections=_PAYMENT, hashtag="TransactionRefundedEvent", load_user=True
    ),
    "TransactionPartiallyRefundedEvent": CardLayout(
        sections=_PAYMENT, hashtag="TransactionRefundedEvent", load_user=True
    ),
    "TransactionFulfilledManuallyEvent": CardLayout(
        details=(
            ("order", _arg("order_id"), True),
            ("admin", _arg("actor"), False),
            ("previous-status", _enum("transaction-status", "previous_status"), False),
        ),
        sections=_SUBSCRIPTION,
    ),
    "PaidOrderNotFulfilledEvent": CardLayout(sections=_PAYMENT, load_user=True),
    "RecurringPaymentUpcomingEvent": CardLayout(sections=_SUBSCRIPTION, load_user=True),
    "RecurringPaymentFailedEvent": CardLayout(sections=_SUBSCRIPTION, load_user=True),
    "RecurringPaymentPausedEvent": CardLayout(sections=_SUBSCRIPTION, load_user=True),
    "RecurringPaymentExhaustedEvent": CardLayout(sections=_SUBSCRIPTION, load_user=True),
    "TelegramUserRegisteredEvent": CardLayout(
        details=(("channel", _const("channel-bot"), False), _AD_LINK, _REFERRAL_CODE),
        hashtag="UserRegisteredEvent",
    ),
    "CabinetUserRegisteredEvent": CardLayout(
        details=(
            ("channel", _const("channel-cabinet"), False),
            ("sign-in-method", _enum("sign-in-method", "method"), False),
            _AD_LINK,
            _REFERRAL_CODE,
        ),
        hashtag="UserRegisteredEvent",
    ),
    "TelegramRegistrationBlockedEvent": CardLayout(
        details=(("channel", _const("channel-bot"), False),),
        hashtag="RegistrationBlockedEvent",
    ),
    "CabinetRegistrationBlockedEvent": CardLayout(
        details=(("channel", _const("channel-cabinet"), False),),
        hashtag="RegistrationBlockedEvent",
    ),
    "SubscriptionFirstConnectedEvent": CardLayout(sections=_SUBSCRIPTION),
    "TorrentBlockerReportEvent": CardLayout(
        details=(_NODE, ("destination", _arg("destination"), True)), sections=_SUBSCRIPTION
    ),
    "SubscriptionExpiredEvent": CardLayout(sections=_SUBSCRIPTION),
    "SubscriptionTrafficLimitedEvent": CardLayout(sections=_SUBSCRIPTION),
    "SubscriptionRevokedEvent": CardLayout(sections=_SUBSCRIPTION),
    "SubscriptionNotConnectedEvent": CardLayout(
        details=(("hours", _arg("hours"), False),), sections=_SUBSCRIPTION
    ),
    "SubscriptionDeviceAddedEvent": CardLayout(sections=frozenset({CardSection.DEVICE})),
    "SubscriptionDeviceRemovedEvent": CardLayout(sections=frozenset({CardSection.DEVICE})),
    "PromocodeActivatedEvent": CardLayout(sections=frozenset({CardSection.PROMOCODE})),
}
_REFUNDS: Final[dict[str, str]] = {
    "TransactionRefundedEvent": "refund-full",
    "TransactionPartiallyRefundedEvent": "refund-partial",
}


def _payment(card: _Card) -> Optional[CardBlock]:
    order = card.data.order
    payload = card.payload
    amount = payload.get("amount") or (order.final_price if order is not None else None)
    currency = payload.get("currency") or (order.currency if order is not None else None)
    order_id = payload.get("order_id") or (order.id if order is not None else None)
    gateway = payload.get("gateway_type") or (order.gateway_type if order is not None else None)
    refund = _REFUNDS.get(card.event_type)
    rows: list[CardRow] = [
        ("ID", "" if order_id is None else str(order_id), True),
        (card.label("payment-method"), card.gateway(gateway), False),
        (card.label("amount"), card.money(amount, currency), False),
        (card.label("refund"), card.label(refund) if refund else "", False),
    ]
    return "💰", card.label("payment"), rows


def _days_left(expire_at: datetime) -> Optional[int]:
    left = (expire_at - datetime_now()).total_seconds()
    return math.ceil(left / 86400) if left > 0 else None


def _subscription(card: _Card) -> Optional[CardBlock]:
    subscription = card.data.subscription
    if subscription is None:
        return None
    limit = card.traffic_limit(subscription.effective_traffic_limit)
    used = card.data.used_traffic
    rows: list[CardRow] = [
        ("ID", str(subscription.id), True),
        (card.label("status"), card.value("subscription-status", subscription.status), False),
        (
            card.label("traffic"),
            limit if used is None else f"{card.traffic(used)} / {limit}",
            False,
        ),
        (card.label("device-limit"), card.count_limit(subscription.effective_device_limit), False),
        (card.label("left"), card.days(_days_left(subscription.expire_at)), False),
    ]
    if subscription.is_trial:
        return "🎁", card.label("trial-subscription"), rows
    return "💳", card.label("subscription"), rows


def _plan_type(traffic_limit: int, device_limit: int) -> str:
    if traffic_limit and device_limit:
        return "BOTH"
    if traffic_limit:
        return "TRAFFIC"
    return "DEVICES" if device_limit else "UNLIMITED"


def _plan_values(card: _Card, plan: dict[str, Any]) -> list[str]:
    traffic, devices = int(plan.get("traffic_limit") or 0), int(plan.get("device_limit") or 0)
    duration = plan.get("duration_days")
    return [
        str(plan.get("name") or ""),
        card.value("plan-type", _plan_type(traffic, devices)),
        card.traffic_limit(traffic),
        card.count_limit(devices),
        card.days(duration if isinstance(duration, int) else None),
    ]


def _plan(card: _Card) -> Optional[CardBlock]:
    if card.data.subscription is None:
        return None
    plan = card.data.subscription.plan_snapshot
    values = _plan_values(card, plan.to_json())
    previous = card.payload.get("previous_plan_snapshot")
    if isinstance(previous, dict):
        # a plan change shows what changed: "old → new"
        values = [
            new if old in ("", new) else f"{old} → {new}"
            for old, new in zip(_plan_values(card, previous), values)
        ]
    labels = ("plan", "type", "traffic-limit", "device-limit", "duration")
    rows: list[CardRow] = [
        (card.label(label), value, label == "plan") for label, value in zip(labels, values)
    ]
    if plan.is_trial:
        return "🎁", card.label("trial-plan"), rows
    return "📦", card.label("plan"), rows


def _promocode_reward(card: _Card) -> str:
    promocode = card.data.promocode
    if promocode is None:
        return ""
    reward = promocode.reward
    match promocode.reward_type:
        case PromocodeRewardType.DURATION:
            return card.days(reward)
        case PromocodeRewardType.TRAFFIC:
            return card.traffic_limit(reward) if reward is not None else ""
        case PromocodeRewardType.DEVICES:
            return "" if reward is None else str(reward)
        case PromocodeRewardType.SUBSCRIPTION:
            return card.days(promocode.reward_duration_days)
        case _:
            return "" if reward is None else f"{reward}%"


def _promocode(card: _Card) -> Optional[CardBlock]:
    promocode = card.data.promocode
    reward_type = card.payload.get("reward_type")
    rows: list[CardRow] = [
        (card.label("code"), promocode.code if promocode is not None else "", True),
        (card.label("type"), card.value("promocode-type", reward_type), False),
        (card.label("reward"), _promocode_reward(card), False),
    ]
    return "🎟", card.label("promocode"), rows


def _device(card: _Card) -> Optional[CardBlock]:
    rows: list[CardRow] = [
        (card.label("hwid"), card.arg("hwid"), True),
        (card.label("platform"), card.arg("platform"), False),
        (card.label("model"), card.arg("device_model"), False),
        (card.label("os-version"), card.arg("os_version"), False),
    ]
    return "📱", card.label("device"), rows


def _build(card: _Card) -> Optional[CardBlock]:
    build = card.build
    if build is None:
        return None
    rows: list[CardRow] = [
        (card.label("version"), build.version, True),
        (card.label("branch"), build.branch or "", False),
        (card.label("commit"), (build.commit or "")[:_COMMIT_LENGTH], True),
        (card.label("build-time"), build.time or "", False),
    ]
    return "🏗️", card.label("build"), rows


def _access(card: _Card) -> Optional[CardBlock]:
    access = card.data.access
    if access is None:
        return None
    rows: list[CardRow] = [
        (card.label("mode"), card.value("access-mode", access.mode), False),
        (
            card.label("payments"),
            card.value("payments", "yes" if access.payments_enabled else "no"),
            False,
        ),
        (
            card.label("registration"),
            card.value("registration", "yes" if access.registration_enabled else "no"),
            False,
        ),
    ]
    return "🔓", card.label("access"), rows


# in the order they appear on the card
_SECTIONS: Final[tuple[tuple[CardSection, Callable[[_Card], Optional[CardBlock]]], ...]] = (
    (CardSection.PAYMENT, _payment),
    (CardSection.SUBSCRIPTION, _subscription),
    (CardSection.PLAN, _plan),
    (CardSection.PROMOCODE, _promocode),
    (CardSection.DEVICE, _device),
    (CardSection.BUILD, _build),
    (CardSection.ACCESS, _access),
)


def _user(card: _Card, *, load_user: bool) -> Optional[CardBlock]:
    # the customer the event is about; the acting admin is already in the details
    snapshot = card.payload.get("target") or card.payload.get("user")
    if not isinstance(snapshot, dict) and load_user and card.data.user is not None:
        user = card.data.user
        snapshot = {
            "id": user.id,
            "name": user.name,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.name,
        }
    if not isinstance(snapshot, dict) or snapshot.get("role") == Role.SYSTEM.name:
        return None
    username = snapshot.get("username")
    rows: list[CardRow] = [
        (card.label("id"), str(snapshot.get("id") or ""), True),
        (card.label("name"), str(snapshot.get("name") or ""), False),
        (card.label("telegram-id"), str(snapshot.get("telegram_id") or ""), True),
        (card.label("username"), f"@{username}" if username else "", False),
        (card.label("email"), str(snapshot.get("email") or ""), False),
    ]
    return "👤", card.label("user"), rows


def plan_summary_block(
    renderer: NotificationRenderer, locale: Locale, subscription: SubscriptionDto
) -> CardBlock:
    """The plan a customer now has, under their own notification."""
    card = _Card(renderer, locale, "", {}, {}, CardData(subscription=subscription), None)
    rows: list[CardRow] = [
        (
            card.label("traffic-limit"),
            card.traffic_limit(subscription.effective_traffic_limit),
            False,
        ),
        (card.label("device-limit"), card.count_limit(subscription.effective_device_limit), False),
        (card.label("left"), card.days(_days_left(subscription.expire_at)), False),
    ]
    return "📦", subscription.plan_snapshot.name, rows


def build_telegram_card(
    renderer: NotificationRenderer,
    locale: Locale,
    *,
    event_type: str,
    payload: dict[str, Any],
    args: dict[str, Union[str, int]],
    data: CardData,
    build: BuildConfig,
    title: str,
    body: str,
    notes: str,
) -> str:
    card = _Card(renderer, locale, event_type, payload, args, data, build)
    layout = LAYOUTS.get(event_type)
    blocks: list[CardBlock] = []
    if layout is not None:
        details = [(card.label(key), value(card), code) for key, value, code in layout.details]
        blocks.append(("ℹ️", card.label("details"), details))
    # the details, then who it is about, then the rest
    user = _user(card, load_user=layout is not None and layout.load_user)
    if user is not None:
        blocks.append(user)
    if layout is not None:
        for section, render in _SECTIONS:
            block = render(card) if section in layout.sections else None
            if block is not None:
                blocks.append(block)
        # the rows say what the sentence did; push keeps the sentence
        body = ""
    return telegram_card(
        f"{card.label('event')}: {title}",
        body,
        emoji=renderer.emoji(locale, event_type) or _DEFAULT_EMOJI,
        hashtag=(layout.hashtag if layout is not None else None) or event_type,
        blocks=blocks,
        quote=renderer.text(locale, f"{message_id(event_type)}.hint"),
        footer=notes.strip() or None,
    )
