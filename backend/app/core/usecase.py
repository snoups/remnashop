from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING, Generic, Optional, TypeVar, overload

from loguru import logger

from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy

if TYPE_CHECKING:
    from app.modules.users.dto import UserDto

InputDto = TypeVar("InputDto")
OutputDto = TypeVar("OutputDto")


@lru_cache(maxsize=1)
def _system_actor() -> UserDto:
    # local import: app.modules.users triggers a package __init__ chain that
    # imports back into this module -- deferred here breaks that cycle,
    # same class of circular import fixed in core/security/permissions.py.
    from app.modules.users.dto import UserDto  # noqa: PLC0415

    return UserDto(
        id=-1,
        telegram_id=-1,
        name=Role.SYSTEM.name,
        role=Role.SYSTEM,
    )


class BoundUseCase(Generic[InputDto, OutputDto]):
    def __init__(self, use_case: "UseCase[InputDto, OutputDto]", actor: UserDto) -> None:
        self._use_case = use_case
        self._actor = actor

    @overload
    async def __call__(self, data: InputDto) -> OutputDto: ...

    @overload
    async def __call__(self) -> OutputDto: ...

    async def __call__(self, data: Optional[InputDto] = None) -> OutputDto:
        return await self._use_case._run(self._actor, data)


class UseCase(ABC, Generic[InputDto, OutputDto]):
    required_permission: Optional[Permission] = None

    @property
    def system(self) -> "BoundUseCase[InputDto, OutputDto]":
        return BoundUseCase(self, _system_actor())

    @overload
    async def __call__(self, actor: UserDto, data: InputDto) -> OutputDto: ...

    @overload
    async def __call__(self, actor: UserDto) -> OutputDto: ...

    async def __call__(self, actor: UserDto, data: Optional[InputDto] = None) -> OutputDto:
        return await self._run(actor, data)

    async def _run(self, actor: UserDto, data: Optional[InputDto] = None) -> OutputDto:
        self._check_permissions(actor)
        # data-less usecases (InputDto=None) are called via the no-data
        # __call__ overload above and never read `data` in _execute(); mypy
        # can't express that relationship, so it sees `InputDto | None`
        # against `_execute`'s `InputDto` parameter.
        return await self._execute(actor, data)  # type: ignore[arg-type]

    def _check_permissions(self, actor: UserDto) -> None:
        if actor.role == Role.SYSTEM:
            logger.debug(
                f"Skipping permission check for system actor in '{self.__class__.__name__}'"
            )
            return

        if self.required_permission is None:
            logger.warning(f"Permission not configured for use case '{self.__class__.__name__}'")
            raise PermissionDeniedError

        if not PermissionPolicy.has_permission(actor, self.required_permission):
            logger.warning(f"Permission denied for actor {actor.log}")
            raise PermissionDeniedError

    @abstractmethod
    async def _execute(self, actor: UserDto, data: InputDto) -> OutputDto:
        raise NotImplementedError
