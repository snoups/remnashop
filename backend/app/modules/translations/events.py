from app.core.enums import Locale
from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.settings.events import LocaleActivatedEvent, LocaleDeactivatedEvent
from app.modules.translations.tasks import (
    copy_locale_translations_task,
    delete_locale_translations_task,
)


async def _on_locale_activated(entry: StoredEvent) -> None:
    # A known dishka+taskiq limitation: mypy can't see that repository/uow
    # are FromDishka-injected and don't belong in .kiq()'s own call signature.
    await copy_locale_translations_task.kiq(  # type: ignore[call-overload]
        source=Locale.EN.value, target=entry.payload["locale"]
    )


async def _on_locale_deactivated(entry: StoredEvent) -> None:
    await delete_locale_translations_task.kiq(locale=entry.payload["locale"])  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(LocaleActivatedEvent, _on_locale_activated)
    bus.subscribe(LocaleDeactivatedEvent, _on_locale_deactivated)
