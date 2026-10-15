from app.modules.notifications.dto import NotificationChannelsDto, effective_matrix
from app.modules.notifications.repository import NotificationRepository
from app.modules.users import UserDto


async def to_channels_dto(
    user: UserDto, repository: NotificationRepository
) -> NotificationChannelsDto:
    return NotificationChannelsDto(
        channels=effective_matrix(user),
        is_push_configured=await repository.is_push_configured(),
        telegram_available=user.telegram_id is not None,
    )
