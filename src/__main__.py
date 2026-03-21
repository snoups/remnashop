import uvicorn
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.fastapi import setup_dishka as setup_fastapi_dishka
from fastapi import FastAPI

from src.core.config import AppConfig
from src.core.logger import setup_logger
from src.infrastructure.di import create_aiogram_container
from src.telegram.dispatcher import get_bg_manager_factory, get_dispatcher, setup_dispatcher
from src.web.app import get_app


def application() -> FastAPI:
    config = AppConfig.get()
    setup_logger(config)

    dispatcher = get_dispatcher(config)
    bg_manager_factory = get_bg_manager_factory(dispatcher)
    setup_dispatcher(dispatcher)

    app = get_app(config, dispatcher)
    container = create_aiogram_container(config, bg_manager_factory)

    setup_aiogram_dishka(container, dispatcher, auto_inject=True)
    setup_fastapi_dishka(container, app)
    return app


if __name__ == "__main__":
    uvicorn.run(
        app=application,
        host="0.0.0.0",
        port=8000,
        factory=True,
    )
