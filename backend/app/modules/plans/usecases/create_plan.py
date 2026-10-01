import secrets
import string
from dataclasses import replace
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import CreatePlanDto, PlanDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository

# A LINK plan is bought by its code alone, so it has to be unguessable -- the
# same 8-character random code main used, never chosen by an admin.
_PUBLIC_CODE_ALPHABET: Final[str] = string.ascii_letters + string.digits
_PUBLIC_CODE_LENGTH: Final[int] = 8


def _generate_public_code() -> str:
    return "".join(secrets.choice(_PUBLIC_CODE_ALPHABET) for _ in range(_PUBLIC_CODE_LENGTH))


class CreatePlanUseCase(UseCase[CreatePlanDto, PlanDto]):
    required_permission = Permission.PLANS_CREATE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: CreatePlanDto) -> PlanDto:
        if data.public_code is None:
            data = replace(data, public_code=_generate_public_code())
        async with self._uow:
            plan = await self._plan_repository.create(data)
            await self._event_publisher.publish(
                PlanChangedEvent(user=actor, action="create", plan_id=plan.id)
            )
        logger.info(f"{actor.log} Created plan '{plan.name}'")
        return plan
