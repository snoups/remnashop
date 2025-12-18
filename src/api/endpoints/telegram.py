import asyncio
import secrets
from typing import Annotated, Any

from aiogram import Bot, Dispatcher
from aiogram.methods import TelegramMethod
from aiogram.types import Update
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Body, FastAPI, Header, HTTPException, Response, status
from loguru import logger


class TelegramWebhookEndpoint:
    dispatcher: Dispatcher
    secret_token: str
    _feed_update_tasks: set[asyncio.Task[Any]]

    def __init__(self, dispatcher: Dispatcher, secret_token: str) -> None:
        self.dispatcher = dispatcher
        self.secret_token = secret_token
        self._feed_update_tasks = set()

    async def startup(self) -> None:
        await self.dispatcher.emit_startup(**self.dispatcher.workflow_data)

    async def shutdown(self) -> None:
        await self.dispatcher.emit_shutdown(**self.dispatcher.workflow_data)

        for task in list(self._feed_update_tasks):
            if not task.done():
                task.cancel()

        await asyncio.gather(*self._feed_update_tasks, return_exceptions=True)

    def register(self, app: FastAPI, path: str) -> None:
        app.add_api_route(path=path, endpoint=self._handle_request, methods=["POST"])

    def _verify_secret(self, telegram_secret_token: str) -> bool:
        return secrets.compare_digest(telegram_secret_token, self.secret_token)

    async def _feed_update(self, bot: Bot, update: Update) -> None:
        result = await self.dispatcher.feed_update(bot=bot, update=update)
        if isinstance(result, TelegramMethod):
            await self.dispatcher.silent_call_request(bot=bot, result=result)

    @inject
    async def _handle_request(
        self,
        update: Annotated[Update, Body()],
        x_telegram_bot_api_secret_token: Annotated[str, Header()],
        bot: FromDishka[Bot],
    ) -> Response:
        if not self._verify_secret(x_telegram_bot_api_secret_token):
            logger.warning(f"Invalid secret token for update '{update.update_id}'")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

        task = asyncio.create_task(self._feed_update(bot=bot, update=update))
        self._feed_update_tasks.add(task)
        task.add_done_callback(self._feed_update_tasks.discard)

        logger.debug(f"Update '{update.update_id}' scheduled for processing")
        return Response(status_code=status.HTTP_200_OK)
