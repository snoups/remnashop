from collections import defaultdict

import httpx
from loguru import logger
from pydantic import ValidationError
from remnapy import RemnawaveSDK
from remnapy.exceptions import ApiError
from remnapy.models import NodeResponseDto

from app.core.actor import Actor
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.overview.dto import CountryCardDto, NodeCardDto, NodesOverviewDto


def _node_cards(nodes: list[NodeResponseDto]) -> list[NodeCardDto]:
    cards = [
        NodeCardDto(
            name=n.name,
            country_code=n.country_code,
            is_connected=n.is_connected,
            is_disabled=n.is_disabled,
            users_online=n.users_online or 0,
            traffic_used_bytes=(
                int(n.traffic_used_bytes) if n.traffic_used_bytes is not None else None
            ),
            last_status_change=n.last_status_change,
        )
        for n in nodes
    ]
    return sorted(cards, key=lambda c: (not c.is_connected, -c.users_online, c.name))


def _countries(cards: list[NodeCardDto]) -> list[CountryCardDto]:
    grouped: defaultdict[str, list[NodeCardDto]] = defaultdict(list)
    for card in cards:
        grouped[card.country_code].append(card)
    countries = [
        CountryCardDto(
            country_code=code,
            nodes=len(group),
            connected=sum(c.is_connected for c in group),
            users_online=sum(c.users_online for c in group),
        )
        for code, group in grouped.items()
    ]
    return sorted(countries, key=lambda c: (-c.users_online, c.country_code))


class GetNodesOverviewUseCase(UseCase[None, NodesOverviewDto]):
    required_permission = Permission.REMNAWAVE_NODES_VIEW

    def __init__(self, remnawave_sdk: RemnawaveSDK) -> None:
        self._remnawave_sdk = remnawave_sdk

    async def _execute(self, actor: Actor, data: None) -> NodesOverviewDto:
        try:
            nodes = list(await self._remnawave_sdk.nodes.get_all_nodes())
        except (
            RemnawavePanelUnavailableError,
            ApiError,
            ValidationError,
            httpx.HTTPError,
        ) as error:
            logger.warning(f"Remnawave response unusable: {type(error).__name__}")
            return NodesOverviewDto(available=False, nodes=[], countries=[])
        cards = _node_cards(nodes)
        return NodesOverviewDto(available=True, nodes=cards, countries=_countries(cards))
