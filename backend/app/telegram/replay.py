import asyncio
from typing import Any, Final

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Message, Update
from loguru import logger

from app.core.utils.time import datetime_now

# keeps the replay tasks referenced until they finish
_replays: Final[set[asyncio.Task[Any]]] = set()


async def _replay(dispatcher: Dispatcher, bot: Bot, message: Message) -> None:
    try:
        await dispatcher.feed_update(bot, Update(update_id=0, message=message))
    except Exception:
        logger.exception(f"Failed to replay a message for chat {message.chat.id}")


def replay_later(dispatcher: Dispatcher, bot: Bot, message: Message) -> None:
    """Feeds the message once the current update is done: its handler holds the
    user's event-isolation lock, a replay awaited inside it would wait on itself."""
    task = asyncio.create_task(_replay(dispatcher, bot, message))
    _replays.add(task)
    task.add_done_callback(_replays.discard)


def start_command(callback: CallbackQuery, payload: str) -> Message:
    """The /start <payload> the presser would send from their private chat, never shown there."""
    return Message(
        message_id=0,
        date=datetime_now(),
        chat=Chat(id=callback.from_user.id, type="private"),
        from_user=callback.from_user,
        text=f"/start {payload}",
    )
