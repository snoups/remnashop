from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.modules.users.events import MarketingOptOutChangedEvent
from app.modules.users.repository import UserRepository
from app.modules.users.unsubscribe import read_unsubscribe_token


class UnsubscribeMarketingUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher

    async def execute(self, token: str) -> None:
        user_id = read_unsubscribe_token(token, self._config.crypt_key.get_secret_value())
        invalid = ValidationError(
            "Invalid unsubscribe link", code=ErrorCode.UNSUBSCRIBE_TOKEN_INVALID
        )
        if user_id is None:
            raise invalid
        async with self._uow:
            user = await self._user_repository.find_by_id(user_id)
            if user is None or user.deleted_at is not None:
                raise invalid
            if user.marketing_opt_out:
                return
            await self._user_repository.set_marketing_opt_out(user_id, True)
            await self._event_publisher.publish(
                MarketingOptOutChangedEvent(user_id=user_id, opted_out=True, source="link")
            )
        logger.info(f"User '{user_id}' unsubscribed from marketing by email link")
