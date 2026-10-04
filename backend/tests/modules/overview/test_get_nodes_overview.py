from types import SimpleNamespace
from typing import Any, Optional, cast

import httpx
import pytest
from pydantic import ValidationError
from remnapy import RemnawaveSDK
from remnapy.models import NodeResponseDto

from app.core.enums import Locale, Role
from app.core.exceptions import PermissionDeniedError, RemnawavePanelUnavailableError
from app.modules.overview.usecases import GetNodesOverviewUseCase
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


class _NodesStub:
    def __init__(self, nodes: list[NodeResponseDto], error: Optional[Exception] = None) -> None:
        self._nodes, self._error = nodes, error

    async def get_all_nodes(self) -> list[NodeResponseDto]:
        if self._error is not None:
            raise self._error
        return self._nodes


def _sdk(stub: _NodesStub) -> RemnawaveSDK:
    return cast(RemnawaveSDK, SimpleNamespace(nodes=stub))


def _node(
    name: str, country: str, *, connected: bool = True, online: Optional[int] = 0, **extra: Any
) -> NodeResponseDto:
    return NodeResponseDto.model_validate(
        {
            "uuid": "00000000-0000-0000-0000-000000000001",
            "id": 1,
            "name": name,
            "address": "1.1.1.1",
            "isConnected": connected,
            "isDisabled": False,
            "isConnecting": False,
            "isTrafficTrackingActive": False,
            "viewPosition": 1,
            "countryCode": country,
            "consumptionMultiplier": 1,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "configProfile": {"activeConfigProfileUuid": None, "activeInbounds": []},
            "usersOnline": online,
            **extra,
        }
    )


async def test_groups_nodes_by_country_and_orders_cards() -> None:
    sdk = _sdk(
        _NodesStub(
            [
                _node("de-b", "DE", connected=False, online=0),
                _node("nl-a", "NL", online=5),
                _node("de-a", "DE", online=9, trafficUsedBytes=1024.0),
            ]
        )
    )

    result = await GetNodesOverviewUseCase(sdk)(OWNER)

    assert result.available is True
    assert [n.name for n in result.nodes] == ["de-a", "nl-a", "de-b"]
    assert result.nodes[0].traffic_used_bytes == 1024
    assert [c.country_code for c in result.countries] == ["DE", "NL"]
    assert (result.countries[0].nodes, result.countries[0].connected) == (2, 1)
    assert result.countries[0].users_online == 9


async def test_missing_users_online_counts_as_zero() -> None:
    result = await GetNodesOverviewUseCase(_sdk(_NodesStub([_node("a", "DE", online=None)])))(OWNER)

    assert result.nodes[0].users_online == 0


async def test_unavailable_panel_is_reported_not_raised() -> None:
    sdk = _sdk(_NodesStub([], RemnawavePanelUnavailableError("down")))

    result = await GetNodesOverviewUseCase(sdk)(OWNER)

    assert result.available is False
    assert result.nodes == [] and result.countries == []


async def test_requires_the_nodes_permission() -> None:
    actor = OWNER.model_copy(update={"permission_revokes": ["REMNAWAVE_NODES_VIEW"]})

    with pytest.raises(PermissionDeniedError):
        await GetNodesOverviewUseCase(_sdk(_NodesStub([])))(actor)


async def test_unparsable_panel_response_is_reported_not_raised() -> None:
    sdk = _sdk(_NodesStub([], ValidationError.from_exception_data("X", [])))

    result = await GetNodesOverviewUseCase(sdk)(OWNER)

    assert result.available is False


async def test_transport_error_before_the_breaker_opens_marks_the_card_unavailable() -> None:
    sdk = _sdk(_NodesStub([], httpx.ConnectError("down")))

    result = await GetNodesOverviewUseCase(sdk)(OWNER)

    assert result.available is False
