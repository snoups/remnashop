import asyncio
from collections import deque
from typing import Callable, Deque, Optional

from loguru import logger

from src.application.dto import NotificationTaskDto
from src.core.constants import BATCH_DELAY, BATCH_SIZE_10
from src.core.utils.iterables import chunked


class NotificationQueue:
    def __init__(self) -> None:
        self._interval = 1.0
        self._queue: Deque[NotificationTaskDto] = deque()
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    def start(self, sender: Callable) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._worker(sender))
            logger.info("Notification worker started")

    async def enqueue(self, task: NotificationTaskDto) -> None:
        async with self._lock:
            self._queue.append(task)

    async def _worker(self, sender: Callable) -> None:
        while True:
            await asyncio.sleep(self._interval)

            async with self._lock:
                if not self._queue:
                    continue

                batch = list(self._queue)
                self._queue.clear()

            logger.debug(f"Processing '{len(batch)}' queued notifications")

            for i, chunk in enumerate(chunked(batch, BATCH_SIZE_10), start=1):
                chunk_start = asyncio.get_running_loop().time()

                results = []
                for task in chunk:
                    try:
                        result = await sender(task)
                        results.append(result)
                    except Exception as e:
                        results.append(e)
                        logger.error(
                            f"Notification task failed: {type(e).__name__}: {e}",
                            exc_info=e,
                        )

                elapsed = asyncio.get_running_loop().time() - chunk_start
                errors = sum(1 for r in results if isinstance(r, Exception))
                logger.debug(
                    f"Chunk '{i}': {len(results) - errors} success, "
                    f"{errors} errors in {elapsed:.2f}s"
                )

                wait_time = BATCH_DELAY - elapsed
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
