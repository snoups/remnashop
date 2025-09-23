from aiogram import Router
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from dishka import FromDishka
from loguru import logger

from src.core.utils.formatters import format_log_user
from src.infrastructure.database.models.dto import UserDto
from src.services.user import UserService

# For only ChatType.PRIVATE (app/bot/filters/private.py)
router = Router(name=__name__)


@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_unblocked(
    member: ChatMemberUpdated,
    user: UserDto,
    user_service: FromDishka[UserService],
) -> None:
    logger.info(f"{format_log_user(user)} Bot unblocked")
    await user_service.set_bot_blocked(user=user, blocked=False)


@router.my_chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_blocked(
    member: ChatMemberUpdated,
    user: UserDto,
    user_service: FromDishka[UserService],
) -> None:
    logger.info(f"{format_log_user(user)} Bot blocked")
    await user_service.set_bot_blocked(user=user, blocked=True)
