import asyncio
import inspect
import pathlib
from dataclasses import dataclass
from typing import ClassVar

import app.modules as modules_package
from app.core.event_bus import EventBus
from app.core.events import BaseEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class _ProbeEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


@dataclass(frozen=True, kw_only=True)
class _OtherEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


async def test_publish_does_not_block_on_a_slow_handler() -> None:
    bus = EventBus()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_handler(event: _ProbeEvent) -> None:
        started.set()
        await release.wait()

    bus.subscribe(_ProbeEvent, slow_handler)

    await asyncio.wait_for(bus.publish(_ProbeEvent()), timeout=1)
    # publish() returned already -- the handler may not have even started yet,
    # but it must not have forced us to wait for its completion.
    release.set()
    await bus.shutdown()


async def test_subscribed_handler_eventually_runs() -> None:
    bus = EventBus()
    received: list[_ProbeEvent] = []

    async def handler(event: _ProbeEvent) -> None:
        received.append(event)

    bus.subscribe(_ProbeEvent, handler)
    await bus.publish(_ProbeEvent())
    await bus.shutdown()

    assert len(received) == 1


async def test_subscribe_all_receives_every_event_type() -> None:
    bus = EventBus()
    received: list[BaseEvent] = []

    async def catch_all(event: BaseEvent) -> None:
        received.append(event)

    bus.subscribe_all(catch_all)
    await bus.publish(_ProbeEvent())
    await bus.publish(_OtherEvent())
    await bus.shutdown()

    assert len(received) == 2


async def test_one_failing_handler_does_not_stop_another() -> None:
    bus = EventBus()
    received: list[_ProbeEvent] = []

    async def failing_handler(event: _ProbeEvent) -> None:
        raise RuntimeError("boom")

    async def working_handler(event: _ProbeEvent) -> None:
        received.append(event)

    bus.subscribe(_ProbeEvent, failing_handler)
    bus.subscribe(_ProbeEvent, working_handler)
    await bus.publish(_ProbeEvent())
    await bus.shutdown()

    assert len(received) == 1


async def test_shutdown_awaits_pending_dispatch_before_clearing() -> None:
    bus = EventBus()
    received: list[_ProbeEvent] = []

    async def slow_handler(event: _ProbeEvent) -> None:
        await asyncio.sleep(0.05)
        received.append(event)

    bus.subscribe(_ProbeEvent, slow_handler)
    await bus.publish(_ProbeEvent())
    await bus.shutdown()

    assert len(received) == 1


def test_autodiscover_registers_every_module_that_defines_subscribers() -> None:
    # Regression guard for EventBus.autodiscover()'s hand-maintained
    # import list (see core/event_bus.py) -- a module that defines its own
    # register_subscribers() but forgets to add itself there would silently
    # never get that specific handler wired up (it'd still show up in the
    # event log via event_log's own catch-all subscriber, but any other
    # module-specific handler, e.g. auth's loguru logging, just wouldn't run).
    modules_dir = pathlib.Path(modules_package.__file__).parent
    modules_with_subscribers = {
        path.parent.name
        for path in modules_dir.glob("*/*.py")
        if "def register_subscribers(" in path.read_text()
    }
    assert modules_with_subscribers, "sanity check: expected to find at least one module"

    autodiscover_source = inspect.getsource(EventBus.autodiscover)
    for module_name in modules_with_subscribers:
        # Matches the aliasing convention every existing registration follows:
        # `register_subscribers as register_<module>_subscribers`, then
        # `register_<module>_subscribers(self)`. Checking for the call (not
        # just the import) is what actually caught this test's own bug during
        # development -- an import-only check stayed green even with the call
        # commented out.
        assert f"register_{module_name}_subscribers(self)" in autodiscover_source, (
            f"'{module_name}' defines register_subscribers() but "
            "EventBus.autodiscover() doesn't appear to call it"
        )
