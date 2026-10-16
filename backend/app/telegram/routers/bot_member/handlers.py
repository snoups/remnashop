from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import KICKED, MEMBER, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from dishka import FromDishka

from app.modules.users import SetBotBlockedDto, SetBotBlockedUseCase

router = Router(name=__name__)
router.my_chat_member.filter(F.chat.type == ChatType.PRIVATE)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def on_bot_blocked(
    update: ChatMemberUpdated, set_bot_blocked: FromDishka[SetBotBlockedUseCase]
) -> None:
    await set_bot_blocked.system(SetBotBlockedDto(telegram_id=update.from_user.id, blocked=True))


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def on_bot_unblocked(
    update: ChatMemberUpdated, set_bot_blocked: FromDishka[SetBotBlockedUseCase]
) -> None:
    await set_bot_blocked.system(SetBotBlockedDto(telegram_id=update.from_user.id, blocked=False))
