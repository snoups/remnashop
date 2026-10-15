from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.emoji_packs.events import EmojiPackChangedEvent
from app.modules.emoji_packs.repository import EmojiPackRepository


class DeleteEmojiPackUseCase(UseCase[str, None]):
    required_permission = Permission.EMOJI_PACKS_DELETE

    def __init__(
        self,
        emoji_pack_repository: EmojiPackRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._emoji_pack_repository = emoji_pack_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: str) -> None:
        async with self._uow:
            if not await self._emoji_pack_repository.delete(data):
                raise NotFoundError(
                    f"Emoji pack not found: {data}", code=ErrorCode.EMOJI_PACK_NOT_FOUND
                )
            await self._event_publisher.publish(
                EmojiPackChangedEvent(actor=actor, action="delete", set_name=data)
            )
