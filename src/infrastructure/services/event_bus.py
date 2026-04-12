import asyncio
import inspect
from collections import defaultdict
from typing import Any, Callable, Optional, Type, TypeVar

from dishka import AsyncContainer
from dishka.registry import Registry
from loguru import logger

from src.application.common import EventPublisher, EventSubscriber
from src.application.events import BaseEvent
from src.application.events.system import ErrorEvent
from src.core.config import AppConfig

F = TypeVar("F", bound=Callable[..., Any])


def on_event(*event_types: Type[BaseEvent]) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        func._event_types = event_types  # type: ignore
        return func

    return decorator


class EventBusImpl(EventPublisher, EventSubscriber):
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._listeners: dict[Type[BaseEvent], list[tuple[Type[Any], Callable]]] = defaultdict(list)
        self._container_factory: Optional[Callable[[], AsyncContainer]] = None
        self._registered_classes: set[Type[Any]] = set()
        self._background_tasks: set[asyncio.Task] = set()
        logger.info("EventBus initialized")

    def set_container_factory(self, factory: Callable[[], AsyncContainer]) -> None:
        self._container_factory = factory

    async def shutdown(self) -> None:
        if not self._background_tasks:
            logger.debug("No background tasks to shut down")
            return

        tasks_count = len(self._background_tasks)
        logger.info(f"Waiting for '{tasks_count}' background tasks to complete")

        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        logger.info("All background tasks completed")

    async def publish(self, event: BaseEvent) -> None:
        if not self._container_factory:
            raise RuntimeError("Container factory not set")

        event_type = type(event)
        targets = []

        for registered_type, handlers in self._listeners.items():
            if isinstance(event, registered_type):
                targets.extend(handlers)

        if not targets:
            logger.debug(f"No listeners found for event '{event_type.__name__}'")
            return

        for service_class, method in targets:
            task = asyncio.create_task(self._handle_event(event, service_class, method))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        logger.info(f"Published event '{event_type.__name__}' to '{len(targets)}' listeners")

    async def _handle_event(
        self,
        event: BaseEvent,
        service_class: Type[Any],
        method: Callable,
    ) -> None:
        if not self._container_factory:
            raise RuntimeError("Container factory not set")

        async with self._container_factory()() as request_container:
            try:
                service_instance = await request_container.get(service_class)
                await method(service_instance, event)
                logger.debug(
                    f"Event '{type(event).__name__}' handled by '{service_class.__name__}'"
                )
            except Exception as e:
                logger.error(
                    f"Error handling event '{type(event).__name__}' "
                    f"in '{service_class.__name__}': '{e}'"
                )
                if not isinstance(event, ErrorEvent):
                    await self.publish(ErrorEvent(**self._config.build.data, exception=e))
                raise

    def autodiscover(self) -> None:
        logger.info("Starting events autodiscovery")
        self._listeners.clear()
        self._registered_classes.clear()

        if not self._container_factory:
            logger.warning("Container factory not set, skipping autodiscovery")
            return

        container = self._container_factory()
        self._scan_registries(container.registry, *container.child_registries)

        total_listeners = sum(len(handlers) for handlers in self._listeners.values())
        logger.info(f"Autodiscovery finished. Total listeners: '{total_listeners}'")

    def _scan_registries(self, *registries: Registry) -> None:
        for registry in registries:
            for key, factory in registry.factories.items():
                if inspect.isclass(key.type_hint):
                    self._scan_and_subscribe(key.type_hint)

                if inspect.isclass(factory.source):
                    self._scan_and_subscribe(factory.source)

    def _scan_and_subscribe(self, service_class: Type[Any]) -> None:
        if service_class in self._registered_classes:
            return

        found = 0
        for attr_name, attr in inspect.getmembers(service_class):
            if hasattr(attr, "_event_types"):
                event_types = getattr(attr, "_event_types")
                for event_type in event_types:
                    handler_key = (service_class, attr)
                    if handler_key not in self._listeners[event_type]:
                        self._listeners[event_type].append(handler_key)
                        found += 1
                        logger.debug(
                            f"Subscribed '{service_class.__name__}.{attr_name}' "
                            f"to '{event_type.__name__}'"
                        )

        if found > 0:
            self._registered_classes.add(service_class)
            logger.info(f"Registered '{found}' listeners from '{service_class.__name__}'")
