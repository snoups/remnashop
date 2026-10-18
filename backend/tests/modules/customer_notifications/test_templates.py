from pathlib import Path

import pytest
from fluent.syntax import FluentParser
from fluent.syntax.ast import Message

from app.core.enums import Locale
from app.core.event_bus import EventBus
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
