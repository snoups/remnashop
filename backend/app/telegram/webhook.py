import asyncio
import secrets
from typing import Annotated, Any, Final

from aiogram import Bot, Dispatcher
from aiogram.methods import TelegramMethod
from aiogram.types import Update
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from loguru import logger
from pydantic import ValidationError

from app.core.constants import MAX_WEBHOOK_BODY_BYTES
from app.core.utils.http import read_bounded_body

_MAX_CONCURRENT_UPDATES: Final[int] = 100


class TelegramWebhookEndpoint:
    def __init__(self, dispatcher: Dispatcher, secret_token: str) -> None:
        self.dispatcher = dispatcher
        self.secret_token = secret_token
        self._feed_update_tasks: set[asyncio.Task[Any]] = set()
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_UPDATES)

    async def startup(self) -> None:
        await self.dispatcher.emit_startup(**self.dispatcher.workflow_data)
        logger.info("Dispatcher startup events emitted")

    async def shutdown(self) -> None:
        await self.dispatcher.emit_shutdown(**self.dispatcher.workflow_data)

        if self._feed_update_tasks:
            for task in self._feed_update_tasks:
                task.cancel()
            await asyncio.gather(*self._feed_update_tasks, return_exceptions=True)

        logger.info(
            f"Dispatcher shutdown complete and '{len(self._feed_update_tasks)}' tasks cleaned up"
        )

    def register(self, app: FastAPI, path: str) -> None:
        app.add_api_route(
            path, endpoint=self._handle_request, methods=["POST"], include_in_schema=False
        )

    def _verify_secret(self, telegram_secret_token: str) -> bool:
        # bytes: compare_digest raises TypeError on a non-ASCII str
        return secrets.compare_digest(telegram_secret_token.encode(), self.secret_token.encode())

    async def _feed_update(self, bot: Bot, update: Update) -> None:
        # a flood must not exhaust DB connections; excess updates queue here

        async with self._semaphore:
            try:
                result = await self.dispatcher.feed_update(bot, update)
                if isinstance(result, TelegramMethod):
                    await result.as_(bot)
            except Exception as e:
                logger.exception(
                    f"Failed to process update '{update.update_id}' due to error '{e}'"
                )

    @inject
    async def _handle_request(
        self,
        request: Request,
        bot: FromDishka[Bot],
        x_telegram_bot_api_secret_token: Annotated[str, Header()] = "",
    ) -> Response:
        # The secret is checked before the body is read: an unauthenticated
        # caller must not get the bot process to buffer and parse anything.
        if not x_telegram_bot_api_secret_token:
            logger.warning("Missing secret token header on webhook request")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token header is missing"
            )

        if not self._verify_secret(x_telegram_bot_api_secret_token):
            logger.warning("Invalid secret token provided on webhook request")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret token"
            )

        body = await read_bounded_body(request, MAX_WEBHOOK_BODY_BYTES)
        try:
            update = Update.model_validate_json(body)
        except ValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Malformed update"
            ) from error

        if len(self._feed_update_tasks) >= _MAX_CONCURRENT_UPDATES:
            # caps task creation, not only the work under _feed_update's
            # semaphore: a client calling this endpoint directly, past
            # Telegram's throttling, could pile up tasks ahead of it
            logger.warning(f"Update queue full, rejecting update '{update.update_id}'")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Server busy"
            )

        task = asyncio.create_task(self._feed_update(bot, update))
        self._feed_update_tasks.add(task)
        task.add_done_callback(self._feed_update_tasks.discard)

        logger.debug(f"Update '{update.update_id}' scheduled for processing")
        return Response(status_code=status.HTTP_200_OK)
