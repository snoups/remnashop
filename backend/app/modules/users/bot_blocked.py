from app.core.ports import EventPublisher
from app.modules.users.events import BotBlockedByUserEvent
from app.modules.users.repository import UserRepository


async def mark_bot_blocked(
    user_repository: UserRepository, event_publisher: EventPublisher, user_id: int
) -> None:
    if await user_repository.set_bot_blocked(user_id, True):
        await event_publisher.publish(BotBlockedByUserEvent(user_id=user_id))
