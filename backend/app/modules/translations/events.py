from app.core.enums import Locale
from app.core.event_bus import EventBus
from app.modules.settings.events import LocaleActivatedEvent, LocaleDeactivatedEvent
from app.modules.translations.tasks import (
    copy_locale_translations_task,
    delete_locale_translations_task,
)


async def _on_locale_activated(event: LocaleActivatedEvent) -> None:
    # A known dishka+taskiq limitation: mypy can't see that repository/uow
    # are FromDishka-injected and don't belong in .kiq()'s own call
    # signature -- same as modules/event_log/subscribers.py.
    await copy_locale_translations_task.kiq(source=Locale.EN.value, target=event.locale.value)  # type: ignore[call-overload]


async def _on_locale_deactivated(event: LocaleDeactivatedEvent) -> None:
    await delete_locale_translations_task.kiq(locale=event.locale.value)  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(LocaleActivatedEvent, _on_locale_activated)
    bus.subscribe(LocaleDeactivatedEvent, _on_locale_deactivated)
