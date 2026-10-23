from app.core.enums import Locale, PurchaseType, Role
from app.core.event_bus import EventBus
from app.modules.settings import AccessSettingsChangedEvent
from app.modules.subscriptions import SubscriptionPurchasedEvent
from app.modules.transactions import subscribers
from app.modules.users import UserDto
from tests.fakes.events import stored_event

_ADMIN = UserDto(id=1, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)


async def test_only_a_reenable_kicks_the_waitlist(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    kicked: list[bool] = []

    async def _kiq() -> None:
        kicked.append(True)

    monkeypatch.setattr(subscribers.notify_payment_waitlist_task, "kiq", _kiq)
    bus = EventBus()
    subscribers.register_subscribers(bus)

    for reenabled in (False, True):
        event = AccessSettingsChangedEvent(
            actor=_ADMIN, changed_fields=["payments_enabled"], payments_reenabled=reenabled
        )
        await bus.dispatch_stored(stored_event(event))

    assert kicked == [True]


async def test_a_paid_delivery_marks_its_order_fulfilled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    kicked: list[dict[str, object]] = []

    async def _kiq(**kwargs: object) -> None:
        kicked.append(kwargs)

    monkeypatch.setattr(subscribers.mark_order_fulfilled_task, "kiq", _kiq)
    bus = EventBus()
    subscribers.register_subscribers(bus)

    for key in ("order-key", None):
        event = SubscriptionPurchasedEvent(
            user=_ADMIN,
            subscription_id=7,
            plan_id=1,
            purchase_type=PurchaseType.NEW,
            payment_key=key,
        )
        await bus.dispatch_stored(stored_event(event))

    assert kicked == [{"payment_key": "order-key", "subscription_id": 7}]
