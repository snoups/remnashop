from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.modules.subscriptions.dto import PanelSquadDto
from app.modules.subscriptions.panel_squads import PanelSquadCatalog, missing_squads
from app.modules.subscriptions.usecases import ListPanelSquadsUseCase


async def test_lists_internal_and_external_squads_by_name(redis: Redis) -> None:
    internal = SimpleNamespace(uuid=uuid4(), name="ALL", kind="internal")
    external = SimpleNamespace(uuid=uuid4(), name="External", kind="external")
    sdk: Any = SimpleNamespace(
        internal_squads=SimpleNamespace(
            get_internal_squads=AsyncMock(return_value=SimpleNamespace(internal_squads=[internal]))
        ),
        external_squads=SimpleNamespace(
            get_external_squads=AsyncMock(return_value=SimpleNamespace(external_squads=[external]))
        ),
    )

    result = await ListPanelSquadsUseCase(PanelSquadCatalog(cast(RemnawaveSDK, sdk), redis)).system(
        None
    )

    assert result == [
        PanelSquadDto(uuid=internal.uuid, name="ALL", kind="internal"),
        PanelSquadDto(uuid=external.uuid, name="External", kind="external"),
    ]


def test_missing_squads_keeps_the_ones_the_panel_lacks() -> None:
    kept, gone, external = uuid4(), uuid4(), uuid4()

    assert missing_squads([kept, gone], external, frozenset({kept})) == [gone, external]
    assert missing_squads([kept], None, frozenset({kept})) == []


async def test_known_squads_are_cached_and_an_outage_checks_nothing(redis: Redis) -> None:
    await redis.delete("subscriptions:panel_squads")
    squad = SimpleNamespace(uuid=uuid4(), name="ALL")
    get_internal = AsyncMock(return_value=SimpleNamespace(internal_squads=[squad]))
    sdk: Any = SimpleNamespace(
        internal_squads=SimpleNamespace(get_internal_squads=get_internal),
        external_squads=SimpleNamespace(
            get_external_squads=AsyncMock(return_value=SimpleNamespace(external_squads=[]))
        ),
    )
    catalog = PanelSquadCatalog(cast(RemnawaveSDK, sdk), redis)

    assert await catalog.known() == frozenset({squad.uuid})
    assert await catalog.missing([squad.uuid, uuid4()], None) != []
    assert get_internal.await_count == 1  # the second read came from the cache

    await redis.delete("subscriptions:panel_squads")
    get_internal.side_effect = RuntimeError("panel down")
    assert await catalog.known() is None
    assert await catalog.missing([uuid4()], None) == []
