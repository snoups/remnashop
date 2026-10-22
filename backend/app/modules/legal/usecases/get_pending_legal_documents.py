from typing import Final, Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TIME_1D
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PurchaseChannel
from app.modules.legal.dto import PendingLegalDocumentsDto
from app.modules.legal.pending import pending_for_user
from app.modules.legal.repository import LegalRepository
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto

# the bot asks on every customer update; an empty answer holds until a document changes
_NOTHING_PENDING_TTL_S: Final[int] = TIME_1D


class GetPendingLegalDocumentsUseCase:
    def __init__(
        self,
        legal_repository: LegalRepository,
        translation_repository: TranslationRepository,
        redis: Redis,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._translation_repository = translation_repository
        self._redis = redis
        self._uow = uow

    async def execute(
        self, user: UserDto, channel: PurchaseChannel, locale: Optional[Locale]
    ) -> PendingLegalDocumentsDto:
        async with self._uow:
            version = await self._legal_repository.documents_version()
            key = f"{REDIS_KEY_PREFIX}legal_ok:{user.id}:{channel}:{locale}:{version}"
            if await self._redis.exists(key):
                return PendingLegalDocumentsDto(documents=[], is_update=False)
            pending = await pending_for_user(
                self._legal_repository, self._translation_repository, user, channel, locale
            )
        if not pending.documents:
            await self._redis.set(key, "1", ex=_NOTHING_PENDING_TTL_S)
        return pending
