from typing import Final, Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistOriginDto, BlacklistOriginsDto, BlacklistRepository
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.dto import (
    BlacklistHitDto,
    BlacklistMatchDto,
    BlacklistMatchOrigin,
    BlacklistMatchPageDto,
    ListBlacklistMatchesDto,
    UserDto,
)

# Role.USER only, like ListUsersUseCase; reconcile never blocks staff anyway.
_ROLES: Final[tuple[Role, ...]] = (Role.USER,)


def identities_of(
    origins: BlacklistOriginsDto, origin: Optional[BlacklistMatchOrigin] = None
) -> tuple[set[int], set[str]]:
    if origin is None:
        return set(origins.telegram_ids), set(origins.emails)

    def matches(found_in: list[BlacklistOriginDto]) -> bool:
        return any((o.source_id is None) == (origin == "manual") for o in found_in)

    return (
        {value for value, found_in in origins.telegram_ids.items() if matches(found_in)},
        {value for value, found_in in origins.emails.items() if matches(found_in)},
    )


def _hits_for(user: UserDto, origins: BlacklistOriginsDto) -> list[BlacklistHitDto]:
    hits: list[BlacklistHitDto] = []
    if user.telegram_id is not None and user.telegram_id in origins.telegram_ids:
        hits.append(
            BlacklistHitDto(
                kind=BlacklistKind.TELEGRAM_ID,
                value=str(user.telegram_id),
                origins=origins.telegram_ids[user.telegram_id],
            )
        )
    if user.email is not None and user.email.lower() in origins.emails:
        hits.append(
            BlacklistHitDto(
                kind=BlacklistKind.EMAIL,
                value=user.email,
                origins=origins.emails[user.email.lower()],
            )
        )
    return hits


class ListBlacklistMatchesUseCase(UseCase[ListBlacklistMatchesDto, BlacklistMatchPageDto]):
    required_permission = Permission.BLACKLIST_MATCHES_VIEW

    def __init__(
        self,
        user_blacklist: UserBlacklistRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_blacklist = user_blacklist
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: ListBlacklistMatchesDto) -> BlacklistMatchPageDto:
        async with self._uow:
            origins = await self._blacklist_repository.identity_origins()
            all_total = await self._user_blacklist.count_matching(
                *identities_of(origins), roles=_ROLES
            )
            manual_total = await self._user_blacklist.count_matching(
                *identities_of(origins, "manual"), roles=_ROLES
            )
            lists_total = await self._user_blacklist.count_matching(
                *identities_of(origins, "lists"), roles=_ROLES
            )
            users, total = await self._user_blacklist.list_matching(
                *identities_of(origins, data.origin),
                roles=_ROLES,
                search=data.search,
                page=data.page,
                page_size=data.page_size,
            )

        return BlacklistMatchPageDto(
            items=[BlacklistMatchDto(user=user, hits=_hits_for(user, origins)) for user in users],
            total=total,
            all_total=all_total,
            manual_total=manual_total,
            lists_total=lists_total,
        )
