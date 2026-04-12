import asyncio
import time

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.application.common import Notifier
from src.application.common.dao import UserDao
from src.application.dto import MessagePayloadDto
from src.core.constants import BATCH_DELAY, BATCH_SIZE_20
from src.core.utils.iterables import chunked
from src.infrastructure.taskiq.broker import broker


@broker.task
@inject(patch_module=True)
async def notify_payments_restored(
    waiting_user_ids: list[int],
    user_dao: FromDishka[UserDao],
    notifier: FromDishka[Notifier],
) -> None:
    users = await user_dao.get_by_telegram_ids(waiting_user_ids)

    if not users:
        logger.debug("No users found for access notification")
        return

    total_users = len(users)
    total_errors = 0
    start_time = time.perf_counter()

    logger.info(f"Starting access broadcast for '{total_users}' users")

    for i, batch in enumerate(chunked(users, BATCH_SIZE_20), start=1):
        batch_start = time.perf_counter()

        tasks = [
            notifier.notify_user(
                user=user,
                payload=MessagePayloadDto(
                    i18n_key="ntf-access.payments-restored",
                    disable_default_markup=False,
                    delete_after=None,
                ),
            )
            for user in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        batch_errors = sum(1 for result in results if isinstance(result, Exception))
        total_errors += batch_errors

        batch_elapsed = time.perf_counter() - batch_start

        logger.info(
            f"Batch '{i}' processed: sent '{len(batch) - batch_errors}' success, "
            f"'{batch_errors}' errors in '{batch_elapsed:.2f}'s"
        )

        wait_time = BATCH_DELAY - batch_elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)

    total_duration = time.perf_counter() - start_time

    logger.info(
        f"Access broadcast for '{total_users}' users completed in '{total_duration:.2f}'s: "
        f"'{total_users - total_errors}' success, '{total_errors}' errors"
    )
