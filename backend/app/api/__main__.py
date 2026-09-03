import uvicorn
from dishka.integrations.fastapi import setup_dishka as setup_fastapi_dishka
from fastapi import FastAPI

from app.api.app import get_app
from app.api.container import create_api_container
from app.core.config import AppConfig
from app.core.logger import setup_logger


def build_application(config: AppConfig) -> FastAPI:
    app = get_app(config)
    container = create_api_container(config)

    setup_fastapi_dishka(container, app)
    return app


def create_app() -> FastAPI:
    config = AppConfig.get()
    setup_logger(config)
    return build_application(config)


if __name__ == "__main__":
    _config = AppConfig.get()

    uvicorn.run(app=create_app, host=_config.host, port=_config.port, factory=True)
