from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.users.repository import UserRepository
from app.modules.users.unsubscribe import read_unsubscribe_token


class UnsubscribeMarketingUseCase:
    def __init__(self, user_repository: UserRepository, uow: UnitOfWork, config: AppConfig) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config

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
            await self._user_repository.set_marketing_opt_out(user_id, True)
        logger.info(f"User '{user_id}' unsubscribed from marketing by email link")
