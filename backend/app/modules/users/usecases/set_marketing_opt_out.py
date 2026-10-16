from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import SetMarketingOptOutDto, UserDto
from app.modules.users.events import MarketingOptOutChangedEvent
from app.modules.users.repository import UserRepository


class SetMarketingOptOutUseCase(UseCase[SetMarketingOptOutDto, None, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: SetMarketingOptOutDto) -> None:
        async with self._uow:
            current = await self._user_repository.find_by_id(actor.id)
            if current is not None and current.marketing_opt_out is data.opted_out:
                return
            await self._user_repository.set_marketing_opt_out(actor.id, data.opted_out)
            await self._event_publisher.publish(
                MarketingOptOutChangedEvent(user=actor, opted_out=data.opted_out, source="account")
            )
        logger.info(f"{actor.log} Set marketing opt-out to {data}")
