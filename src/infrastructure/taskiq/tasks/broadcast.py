import asyncio
from typing import cast

from aiogram import Bot
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.core.constants import BATCH_DELAY, BATCH_SIZE
from src.core.enums import BroadcastMessageStatus, BroadcastStatus
from src.core.utils.iterables import chunked
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import BroadcastDto, BroadcastMessageDto, UserDto
from src.infrastructure.taskiq.broker import broker
from src.services.broadcast import BroadcastService
from src.services.notification import NotificationService


@broker.task
@inject
async def send_broadcast_task(
    broadcast: BroadcastDto,
    users: list[UserDto],
    payload: MessagePayload,
    notification_service: FromDishka[NotificationService],
    broadcast_service: FromDishka[BroadcastService],
) -> None:
    broadcast_id = cast(int, broadcast.id)
    total_users = len(users)

    logger.info(f"Started sending broadcast '{broadcast_id}', total users: '{total_users}'")

    try:
        broadcast_messages = await broadcast_service.create_messages(
            broadcast_id,
            [
                BroadcastMessageDto(user_id=user.telegram_id, status=BroadcastMessageStatus.PENDING)
                for user in users
            ],
        )
        logger.debug(
            f"Created '{len(broadcast_messages)}' message DTOs for broadcast '{broadcast_id}'"
        )
    except Exception:
        logger.error(
            f"Failed to create message DTOs for broadcast '{broadcast_id}'",
            exc_info=True,
        )
        broadcast.status = BroadcastStatus.ERROR
        await broadcast_service.update(broadcast)
        return

    user_message_pairs = zip(users, broadcast_messages)

    try:
        total_batches = (total_users + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_index, batch in enumerate(chunked(user_message_pairs, BATCH_SIZE)):
            batch_number = batch_index + 1
            batch_size = len(batch)

            logger.info(
                f"Processing broadcast '{broadcast_id}' batch "
                f"{batch_number}/{total_batches}, size: '{batch_size}'"
            )

            for user, message in batch:
                user_id = user.telegram_id

                status = await broadcast_service.get_status(broadcast.task_id)

                if status == BroadcastStatus.CANCELED:
                    logger.warning(f"Broadcast '{broadcast_id}' canceled, terminating task")
                    broadcast.status = BroadcastStatus.CANCELED
                    await broadcast_service.update(broadcast)
                    return

                try:
                    tg_message = await notification_service.notify_user(user=user, payload=payload)

                    if tg_message:
                        message.message_id = tg_message.message_id
                        message.status = BroadcastMessageStatus.SENT
                        broadcast.success_count += 1
                        logger.debug(
                            f"Msg SENT to user '{user_id}' "
                            f"(ID: '{tg_message.message_id}') for broadcast '{broadcast_id}'"
                        )
                    else:
                        message.status = BroadcastMessageStatus.FAILED
                        broadcast.failed_count += 1
                        logger.debug(
                            f"Msg FAILED for user '{user_id}' on broadcast '{broadcast_id}'"
                        )
                except Exception:
                    message.status = BroadcastMessageStatus.FAILED
                    broadcast.failed_count += 1
                    logger.error(
                        f"Exception notifying user '{user_id}' for broadcast '{broadcast_id}'",
                        exc_info=True,
                    )

                try:
                    await broadcast_service.update_message(broadcast_id, message)
                except Exception:
                    logger.error(
                        f"Failed to update message status for user '{user_id}', "
                        f"broadcast '{broadcast_id}'",
                        exc_info=True,
                    )

            await asyncio.sleep(BATCH_DELAY)
            await broadcast_service.update(broadcast)

        broadcast.status = BroadcastStatus.COMPLETED
        await broadcast_service.update(broadcast)
        logger.info(
            f"Broadcast '{broadcast_id}' COMPLETED. "
            f"Success: '{broadcast.success_count}', Failed: ''{broadcast.failed_count}"
        )

    except Exception:
        logger.error(
            f"Unhandled exception during broadcast '{broadcast_id}' execution",
            exc_info=True,
        )
        broadcast.status = BroadcastStatus.ERROR
        await broadcast_service.update(broadcast)


@broker.task
@inject
async def delete_broadcast_task(
    broadcast: BroadcastDto,
    bot: FromDishka[Bot],
    broadcast_service: FromDishka[BroadcastService],
) -> tuple[int, int, int]:
    broadcast_id = cast(int, broadcast.id)
    logger.info(f"Started deleting messages for broadcast '{broadcast_id}'")

    deleted_count = 0
    failed_count = 0

    if not broadcast.messages:
        logger.error(f"Messages list is empty for broadcast '{broadcast_id}', aborting deletion")
        raise ValueError(f"Broadcast '{broadcast_id}' messages is empty")

    total_messages = len(broadcast.messages)

    for message in broadcast.messages:
        user_id = message.user_id
        message_id = message.message_id
        current_status = message.status.value

        if message.status not in (BroadcastMessageStatus.SENT, BroadcastMessageStatus.EDITED):
            logger.debug(f"Skipping deletion for user '{user_id}'. Status: '{current_status}'")
            continue

        if not message_id:
            logger.warning(f"Skipping deletion for user '{user_id}'. No message_id found")
            continue

        try:
            deleted = await bot.delete_message(chat_id=user_id, message_id=message_id)

            if deleted:
                message.status = BroadcastMessageStatus.DELETED
                await broadcast_service.update_message(
                    broadcast_id=broadcast_id,
                    message=message,
                )
                deleted_count += 1
                logger.debug(
                    f"Message DELETED for user '{user_id}'. "
                    f"ID: '{message_id}', broadcast '{broadcast_id}'"
                )
            else:
                failed_count += 1
                logger.debug(
                    f"Deletion FAILED for user '{user_id}'. "
                    f"ID: '{message_id}', broadcast '{broadcast_id}'"
                )
        except Exception:
            failed_count += 1
            logger.error(
                f"Exception during message deletion for user '{user_id}'. "
                f"ID: '{message_id}', broadcast '{broadcast_id}'",
                exc_info=True,
            )

    logger.info(
        f"Deletion finished for broadcast '{broadcast_id}'. "
        f"Total: '{total_messages}', Deleted: '{deleted_count}', Failed: '{failed_count}'"
    )

    return total_messages, deleted_count, failed_count


@broker.task(schedule=[{"cron": "0 0 */7 * *"}])
@inject
async def delete_broadcasts_task(broadcast_service: FromDishka[BroadcastService]) -> None:
    broadcasts = await broadcast_service.get_all()

    if not broadcasts:
        logger.debug("No broadcasts found to delete")
        return

    old_broadcasts = [bc for bc in broadcasts if bc.has_old]
    logger.debug(f"Found '{len(old_broadcasts)}' old broadcasts to delete")

    for broadcast in old_broadcasts:
        await broadcast_service.delete_broadcast(broadcast.id)  # type: ignore[arg-type]
        logger.debug(f"Broadcast '{broadcast.id}' deleted")
