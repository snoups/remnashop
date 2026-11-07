import asyncio
import json
from collections.abc import Sequence
from typing import Final, Optional
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.modules.subscriptions.dto import PanelSquadDto

_CACHE_KEY: Final[str] = "subscriptions:panel_squads"
# the catalog and checkout read it on every page: a deleted squad shows up within a minute
_CACHE_TTL_S: Final[int] = 60


def missing_squads(
    internal: Sequence[UUID], external: Optional[UUID], known: frozenset[UUID]
) -> list[UUID]:
    wanted = [*internal, *([external] if external is not None else [])]
    return [squad for squad in wanted if squad not in known]


class PanelSquadCatalog:
    """The squads the panel has: plans and subscriptions keep only their uuids."""

    def __init__(self, remnawave_sdk: RemnawaveSDK, redis: Redis) -> None:
        self._remnawave_sdk = remnawave_sdk
        self._redis = redis

    async def fetch(self) -> list[PanelSquadDto]:
        internal, external = await asyncio.gather(
            self._remnawave_sdk.internal_squads.get_internal_squads(),
            self._remnawave_sdk.external_squads.get_external_squads(),
        )
        return [
            *(
                PanelSquadDto(uuid=squad.uuid, name=squad.name, kind="internal")
                for squad in internal.internal_squads
            ),
            *(
                PanelSquadDto(uuid=squad.uuid, name=squad.name, kind="external")
                for squad in external.external_squads
            ),
        ]

    async def known(self) -> Optional[frozenset[UUID]]:
        """Cached uuids; None when the panel can't be read, so nobody is blocked by an outage."""
        cached = await self._redis.get(_CACHE_KEY)
        if cached is not None:
            return frozenset(UUID(squad) for squad in json.loads(cached))
        try:
            squads = await self.fetch()
        except Exception as error:
            logger.warning(f"Panel squads unreadable, not checked: {error}")
            return None
        uuids = frozenset(squad.uuid for squad in squads)
        await self._redis.set(
            _CACHE_KEY, json.dumps([str(squad) for squad in uuids]), ex=_CACHE_TTL_S
        )
        return uuids

    async def missing(self, internal: Sequence[UUID], external: Optional[UUID]) -> list[UUID]:
        if not internal and external is None:
            return []
        known = await self.known()
        return [] if known is None else missing_squads(internal, external, known)
