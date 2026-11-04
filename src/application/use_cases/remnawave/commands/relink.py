from collections import defaultdict
from typing import Optional

from loguru import logger
from remnapy.models import UserResponseDto

from src.application.common import Interactor, Remnawave
from src.application.common.dao import SubscriptionDao
from src.application.common.uow import UnitOfWork
from src.application.dto import UnlinkedSubscriptionDto, UserDto

PANEL_PAGE_SIZE = 500


def _short_uuid_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


class RelinkRemnaUsers(Interactor[None, dict[str, int]]):
    """Link subscriptions created for Remnawave 2.x (UUID-based) to 3.x numeric user ids.

    Migration 0041 resets ``user_remna_id`` to ``0`` for every subscription because the
    UUID -> id mapping is only known to the panel. Each current subscription is matched to
    a panel user by subscription URL, short UUID, username and finally a unique telegram ID.
    Subscriptions that cannot be matched stay unlinked; a bot -> panel sync recreates them.
    """

    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ) -> None:
        self.uow = uow
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, data: None) -> dict[str, int]:
        async with self.uow:
            unlinked = await self.subscription_dao.get_unlinked_current()

        if not unlinked:
            return {"total": 0, "linked": 0, "unresolved": 0}

        logger.info(f"Relinking '{len(unlinked)}' subscriptions to Remnawave 3.x user ids")
        index = _PanelUsersIndex(await self._fetch_all_panel_users())

        linked = 0
        unresolved = 0

        async with self.uow:
            for item in unlinked:
                remna_id = index.match(item)

                if remna_id is None or await self.subscription_dao.exists(remna_id):
                    unresolved += 1
                    logger.warning(
                        f"Could not link subscription '{item.subscription_id}' of user "
                        f"{item.user.log} to a Remnawave user"
                    )
                    continue

                await self.subscription_dao.set_remna_id(item.subscription_id, remna_id)
                linked += 1

            await self.uow.commit()

        result = {"total": len(unlinked), "linked": linked, "unresolved": unresolved}
        logger.info(f"Relinking finished: {result}")
        return result

    async def _fetch_all_panel_users(self) -> list[UserResponseDto]:
        users: list[UserResponseDto] = []
        offset = 0

        while True:
            page = await self.remnawave.get_all_users(limit=PANEL_PAGE_SIZE, offset=offset)
            users.extend(page)

            if len(page) < PANEL_PAGE_SIZE:
                return users
            offset += PANEL_PAGE_SIZE


class _PanelUsersIndex:
    def __init__(self, users: list[UserResponseDto]) -> None:
        self.by_url = {u.subscription_url: u.id for u in users}
        self.by_short_uuid = {u.short_uuid: u.id for u in users}
        self.by_username = {u.username: u.id for u in users}
        self.by_telegram_id: dict[int, list[int]] = defaultdict(list)

        for u in users:
            if u.telegram_id is not None:
                self.by_telegram_id[u.telegram_id].append(u.id)

        self._used: set[int] = set()

    def match(self, item: UnlinkedSubscriptionDto) -> Optional[int]:
        candidates = (
            self.by_url.get(item.url),
            self.by_short_uuid.get(_short_uuid_from_url(item.url)),
            self.by_username.get(item.user.remna_name),
            self._unique_telegram_match(item.user.telegram_id),
        )

        for remna_id in candidates:
            if remna_id is not None and remna_id not in self._used:
                self._used.add(remna_id)
                return remna_id

        return None

    def _unique_telegram_match(self, telegram_id: Optional[int]) -> Optional[int]:
        if telegram_id is None:
            return None

        ids = self.by_telegram_id.get(telegram_id, [])
        return ids[0] if len(ids) == 1 else None
