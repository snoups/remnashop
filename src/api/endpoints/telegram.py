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
            path=path,
            endpoint=self._handle_request,
            methods=["POST"],
            include_in_schema=False,
        )

    def _verify_secret(self, telegram_secret_token: str) -> bool:
        return secrets.compare_digest(telegram_secret_token, self.secret_token)

    async def _feed_update(self, bot: Bot, update: Update) -> None:
        try:
            result = await self.dispatcher.feed_update(bot=bot, update=update)
            if isinstance(result, TelegramMethod):
                await result.as_(bot)
        except Exception as exception:
            logger.exception(
                f"Failed to process update '{update.update_id}' due to error '{exception}'"
            )

    @inject
    async def _handle_request(
        self,
        update: Annotated[Update, Body()],
        bot: FromDishka[Bot],
        x_telegram_bot_api_secret_token: Annotated[str, Header()] = "",
    ) -> Response:
        if not x_telegram_bot_api_secret_token:
            logger.warning(f"Missing secret token header for update '{update.update_id}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token header is missing"
            )

        if not self._verify_secret(x_telegram_bot_api_secret_token):
            logger.warning(f"Invalid secret token provided for update '{update.update_id}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret token"
            )

        task = asyncio.create_task(self._feed_update(bot=bot, update=update))
        self._feed_update_tasks.add(task)
        task.add_done_callback(self._feed_update_tasks.discard)

        logger.debug(f"Update '{update.update_id}' scheduled for processing")
        return Response(status_code=status.HTTP_200_OK)
