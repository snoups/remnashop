import asyncio
from typing import Optional, cast

from aiogram import Bot
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

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
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    logger.info(f"Started sending broadcast '{broadcast_id}', total users: {total_users}")

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
        logger.exception(f"Failed to create message DTOs for broadcast '{broadcast_id}'")
        broadcast.status = BroadcastStatus.ERROR
        await broadcast_service.update(broadcast)
        return

    async def send_message(user: UserDto, message: BroadcastMessageDto) -> None:
        try:
            tg_message = await notification_service.notify_user(user=user, payload=payload)
            if tg_message:
                message.message_id = tg_message.message_id
                message.status = BroadcastMessageStatus.SENT
            else:
                message.status = BroadcastMessageStatus.FAILED
        except Exception:
            logger.exception(
                f"Failed to send broadcast '{broadcast_id}' message for '{user.telegram_id}'",
            )
            message.status = BroadcastMessageStatus.FAILED

    user_message_pairs = list(zip(users, broadcast_messages))
    last_known_status: Optional[BroadcastStatus] = broadcast.status

    for i, batch in enumerate(chunked(user_message_pairs, 20), start=1):
        batch_start = loop.time()

        last_known_status = await broadcast_service.get_status(broadcast.task_id)
        if last_known_status == BroadcastStatus.CANCELED:
            break

        tasks = [send_message(u, m) for u, m in batch]
        await asyncio.gather(*tasks)

        _, messages_batch = zip(*batch)
        await broadcast_service.bulk_update_messages(list(messages_batch))

        batch_elapsed = loop.time() - batch_start
        logger.info(f"Batch {i}: sent {len(batch)} messages in {batch_elapsed:.2f}s")

        wait_time = 1.0 - batch_elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)

    broadcast.success_count = sum(
        1 for m in broadcast_messages if m.status == BroadcastMessageStatus.SENT
    )
    broadcast.failed_count = sum(
        1 for m in broadcast_messages if m.status == BroadcastMessageStatus.FAILED
    )

    broadcast.status = (
        BroadcastStatus.CANCELED
        if last_known_status == BroadcastStatus.CANCELED
        else BroadcastStatus.COMPLETED
    )

    await broadcast_service.update(broadcast)

    total_elapsed = loop.time() - start_time
    logger.info(
        f"Finished broadcast '{broadcast_id}' in {total_elapsed:.2f}s "
        f"(sent: {broadcast.success_count}, failed: {broadcast.failed_count})"
    )


@broker.task
@inject
async def delete_broadcast_task(
    broadcast: BroadcastDto,
    bot: FromDishka[Bot],
    broadcast_service: FromDishka[BroadcastService],
) -> tuple[int, int, int]:
    broadcast_id = cast(int, broadcast.id)
    logger.info(f"Started deleting messages for broadcast '{broadcast_id}'")

    if not broadcast.messages:
        logger.error(f"Messages list is empty for broadcast '{broadcast_id}', aborting")
        raise ValueError(f"Broadcast '{broadcast_id}' messages is empty")

    deleted_count = 0
    failed_count = 0
    total_messages = len(broadcast.messages)
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    async def delete_message(message: BroadcastMessageDto) -> BroadcastMessageDto:
        user_id = message.user_id
        message_id = message.message_id

        if message.status not in (BroadcastMessageStatus.SENT, BroadcastMessageStatus.EDITED):
            return message
        if not message_id:
            logger.warning(f"Skipping deletion for user '{user_id}'. No 'message_id'")
            return message

        try:
            deleted = await bot.delete_message(chat_id=user_id, message_id=message_id)
            if deleted:
                message.status = BroadcastMessageStatus.DELETED
            else:
                logger.debug(f"Deletion FAILED for user '{user_id}'. ID: '{message_id}'")
        except Exception:
            logger.exception(f"Exception deleting message for user '{user_id}'. ID: '{message_id}'")
        return message

    for i, batch in enumerate(chunked(broadcast.messages, 20), start=1):
        batch_start = loop.time()
        tasks = [delete_message(m) for m in batch]
        results = await asyncio.gather(*tasks)

        deleted_count += sum(1 for m in results if m.status == BroadcastMessageStatus.DELETED)
        failed_count += sum(1 for m in results if m.status != BroadcastMessageStatus.DELETED)
        await broadcast_service.bulk_update_messages(results)

        batch_elapsed = loop.time() - batch_start
        logger.info(f"Batch {i}: processed {len(batch)} messages in {batch_elapsed:.2f}s")

        wait_time = 1.0 - batch_elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)

    total_elapsed = loop.time() - start_time
    logger.info(
        f"Deletion finished for broadcast '{broadcast_id}'. "
        f"Total: {total_messages}, Deleted: {deleted_count}, Failed: {failed_count}, "
        f"Total time: {total_elapsed:.2f}s"
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
