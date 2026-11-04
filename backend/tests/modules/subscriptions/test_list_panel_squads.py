from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

from remnapy import RemnawaveSDK

from app.modules.subscriptions.dto import PanelSquadDto
from app.modules.subscriptions.usecases import ListPanelSquadsUseCase


async def test_lists_internal_and_external_squads_by_name() -> None:
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

    result = await ListPanelSquadsUseCase(cast(RemnawaveSDK, sdk)).system(None)

    assert result == [
        PanelSquadDto(uuid=internal.uuid, name="ALL", kind="internal"),
        PanelSquadDto(uuid=external.uuid, name="External", kind="external"),
    ]
