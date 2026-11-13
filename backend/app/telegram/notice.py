import asyncio
import html
from contextlib import suppress
from typing import Any, Final, Optional

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

_NOTICE_TTL_S: Final[int] = 5
# keeps the deletion tasks referenced until they finish
_deletions: Final[set[asyncio.Task[Any]]] = set()


async def _delete_after(message: Message, seconds: int) -> None:
    await asyncio.sleep(seconds)
    with suppress(TelegramAPIError):
        await message.delete()


def delete_later(message: Message, seconds: int) -> None:
    """Removes a sent message after `seconds`; a restart before then leaves it in the chat."""
    task = asyncio.create_task(_delete_after(message, seconds))
    _deletions.add(task)
    task.add_done_callback(_deletions.discard)


async def answer_notice(
    event: Optional[TelegramObject],
    text: str,
    *,
    keep: bool = False,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    # a restart within the TTL leaves the message in the chat
    body = f"<i>{html.escape(text)}</i>"
    if isinstance(event, Message):
        sent = await event.answer(body, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    elif isinstance(event, CallbackQuery) and event.bot is not None:
        try:
            sent = await event.bot.send_message(
                event.from_user.id, body, parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
        except TelegramAPIError:
            # a press on a channel post by someone the bot can't write to
            await event.answer(text, show_alert=True)
            return
        await event.answer()
    else:
        return
    if keep:
        return
    delete_later(sent, _NOTICE_TTL_S)
