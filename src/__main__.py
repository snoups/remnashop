import uvicorn
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.fastapi import setup_dishka as setup_fastapi_dishka
from fastapi import FastAPI

from src.api.app import create_app
from src.bot.dispatcher import create_bg_manager_factory, create_dispatcher, setup_dispatcher
from src.core.config import AppConfig
from src.core.logger import setup_logger
from src.infrastructure.di import create_container


def application() -> FastAPI:
    setup_logger()

    config = AppConfig.get()
    dispatcher = create_dispatcher(config=config)
    bg_manager_factory = create_bg_manager_factory(dispatcher=dispatcher)
    setup_dispatcher(dispatcher)

    app = create_app(config=config, dispatcher=dispatcher)
    container = create_container(config=config, bg_manager_factory=bg_manager_factory)

    setup_aiogram_dishka(container=container, router=dispatcher, auto_inject=True)
    setup_fastapi_dishka(container=container, app=app)
    return app


if __name__ == "__main__":
    uvicorn.run(
        app=application,
        host="0.0.0.0",
        port=8000,
        factory=True,
    )
