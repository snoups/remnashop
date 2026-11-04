from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import UserOAuthProviderDao
from src.application.dto.user import UserOAuthProviderDto
from src.core.enums import OAuthProvider
from src.infrastructure.database.models import UserOAuthProvider


class UserOAuthProviderDaoImpl(UserOAuthProviderDao):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
        redis: Redis,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort
        self.redis = redis

        self._convert_to_dto = self.conversion_retort.get_converter(
            UserOAuthProvider,
            UserOAuthProviderDto,
        )

    async def create(self, dto: UserOAuthProviderDto) -> UserOAuthProviderDto:
        db_record = UserOAuthProvider(
            user_id=dto.user_id,
            provider=dto.provider,
            provider_id=dto.provider_id,
        )
        self.session.add(db_record)
        await self.session.flush()

        logger.debug(f"Created OAuth provider '{dto.provider}' for user_id '{dto.user_id}'")
        return self._convert_to_dto(db_record)

    async def delete(self, user_id: int, provider: OAuthProvider) -> bool:
        stmt = (
            delete(UserOAuthProvider)
            .where(
                UserOAuthProvider.user_id == user_id,
                UserOAuthProvider.provider == provider,
            )
            .returning(UserOAuthProvider.id)
        )
        result = await self.session.execute(stmt)
        deleted_id = result.scalar_one_or_none()

        if deleted_id:
            logger.debug(f"Deleted OAuth provider '{provider}' for user_id '{user_id}'")
            return True

        logger.debug(f"OAuth provider '{provider}' not found for user_id '{user_id}'")
        return False
