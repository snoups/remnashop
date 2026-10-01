from dataclasses import dataclass, field
from typing import Literal, Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistOriginDto, BlacklistOriginsDto, BlacklistRepository
from app.modules.users.dto import DEFAULT_PAGE_SIZE, UserDto
from app.modules.users.repository import UserRepository

# Role.USER only -- same staff-visibility rule as ListUsersUseCase, and
# reconcile never blocks staff anyway.
_ROLES: list[Role] = [Role.USER]

BlacklistMatchOrigin = Literal["manual", "lists"]


@dataclass(frozen=True, kw_only=True)
class ListBlacklistMatchesInput:
    search: Optional[str] = None
    # unset = every origin
    origin: Optional[BlacklistMatchOrigin] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class BlacklistHitDto:
    kind: BlacklistKind
    value: str
    origins: list[BlacklistOriginDto] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BlacklistMatchDto:
    user: UserDto
    hits: list[BlacklistHitDto] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BlacklistMatchPageDto:
    items: list[BlacklistMatchDto]
    total: int
    all_total: int
    manual_total: int
    lists_total: int


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


class ListBlacklistMatchesUseCase(UseCase[ListBlacklistMatchesInput, BlacklistMatchPageDto]):
    required_permission = Permission.BLACKLIST_MATCHES_VIEW

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListBlacklistMatchesInput
    ) -> BlacklistMatchPageDto:
        async with self._uow:
            origins = await self._blacklist_repository.identity_origins()
            all_total = await self._user_repository.count_matching(
                *identities_of(origins), roles=_ROLES
            )
            manual_total = await self._user_repository.count_matching(
                *identities_of(origins, "manual"), roles=_ROLES
            )
            lists_total = await self._user_repository.count_matching(
                *identities_of(origins, "lists"), roles=_ROLES
            )
            users, total = await self._user_repository.list_matching(
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
