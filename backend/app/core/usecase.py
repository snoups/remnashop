from abc import ABC, abstractmethod
from typing import Generic, Optional, cast, overload

from loguru import logger
from typing_extensions import TypeVar

from app.core.actor import SYSTEM_ACTOR, Actor
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy

InputDto = TypeVar("InputDto")
OutputDto = TypeVar("OutputDto")
# A usecase that acts on the caller's own account narrows this to UserDto; its
# route then resolves the actor through get_current_user, so an API token never
# reaches it.
ActorT = TypeVar("ActorT", bound=Actor, default=Actor)


class BoundUseCase(Generic[InputDto, OutputDto, ActorT]):
    def __init__(self, use_case: "UseCase[InputDto, OutputDto, ActorT]", actor: ActorT) -> None:
        self._use_case = use_case
        self._actor = actor

    @overload
    async def __call__(self, data: InputDto) -> OutputDto: ...

    @overload
    async def __call__(self) -> OutputDto: ...

    async def __call__(self, data: Optional[InputDto] = None) -> OutputDto:
        return await self._use_case._run(self._actor, data)


class UseCase(ABC, Generic[InputDto, OutputDto, ActorT]):
    required_permission: Optional[Permission] = None

    @property
    def system(self) -> "BoundUseCase[InputDto, OutputDto, ActorT]":
        # only ever reached with the default ActorT; a UserDto-narrowed usecase
        # acts on a real account and has no system caller
        return BoundUseCase(self, cast(ActorT, SYSTEM_ACTOR))

    @overload
    async def __call__(self, actor: ActorT, data: InputDto) -> OutputDto: ...

    @overload
    async def __call__(self, actor: ActorT) -> OutputDto: ...

    async def __call__(self, actor: ActorT, data: Optional[InputDto] = None) -> OutputDto:
        return await self._run(actor, data)

    async def _run(self, actor: ActorT, data: Optional[InputDto] = None) -> OutputDto:
        self._check_permissions(actor)
        # data-less usecases (InputDto=None) are called via the no-data
        # __call__ overload above and never read `data` in _execute(); mypy
        # can't express that relationship, so it sees `InputDto | None`
        # against `_execute`'s `InputDto` parameter.
        return await self._execute(actor, data)  # type: ignore[arg-type]

    def _check_permissions(self, actor: Actor) -> None:
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
    async def _execute(self, actor: ActorT, data: InputDto) -> OutputDto:
        raise NotImplementedError
