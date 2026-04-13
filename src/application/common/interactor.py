from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar, overload

from loguru import logger

from src.application.common.policy import Permission, PermissionPolicy
from src.application.dto import UserDto
from src.core.enums import Role
from src.core.exceptions import PermissionDeniedError

InputDto = TypeVar("InputDto")
OutputDto = TypeVar("OutputDto")

SYSTEM_ACTOR = UserDto(
    id=-1,
    telegram_id=-1,
    name=Role.SYSTEM.name,
    role=Role.SYSTEM,
)


class BoundInteractor(Generic[InputDto, OutputDto]):
    def __init__(self, interactor: "Interactor[InputDto, OutputDto]", actor: UserDto) -> None:
        self._interactor = interactor
        self._actor = actor

    @overload
    async def __call__(self, data: InputDto) -> OutputDto: ...

    @overload
    async def __call__(self) -> OutputDto: ...

    async def __call__(self, data: Optional[InputDto] = None) -> OutputDto:
        return await self._interactor._run(self._actor, data)


class Interactor(ABC, Generic[InputDto, OutputDto]):
    required_permission: Optional[Permission] = None

    @property
    def system(self) -> "BoundInteractor[InputDto, OutputDto]":
        return BoundInteractor(self, SYSTEM_ACTOR)

    @overload
    async def __call__(self, actor: UserDto, data: InputDto) -> OutputDto: ...

    @overload
    async def __call__(self, actor: UserDto) -> OutputDto: ...

    async def __call__(self, actor: UserDto, data: Optional[InputDto] = None) -> OutputDto:
        return await self._run(actor, data)

    async def _run(self, actor: UserDto, data: Optional[InputDto] = None) -> OutputDto:
        self._check_permissions(actor)
        return await self._execute(actor, data)  # type: ignore

    def _check_permissions(self, actor: UserDto) -> None:
        if actor.role == Role.SYSTEM:
            logger.debug(
                f"Skipping permission check for system actor in '{self.__class__.__name__}'"
            )
            return

        if self.required_permission is None:
            logger.warning(f"Permission not configured for interactor '{self.__class__.__name__}'")
            raise PermissionDeniedError

        if not PermissionPolicy.has_permission(actor, self.required_permission):
            logger.warning(
                f"Permission denied for actor '{actor.telegram_id}' with role '{actor.role}'"
            )
            raise PermissionDeniedError

    @abstractmethod
    async def _execute(self, actor: UserDto, data: InputDto) -> OutputDto:
        raise NotImplementedError
