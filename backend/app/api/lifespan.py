from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka import AsyncContainer, Scope
from fastapi import FastAPI

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.ports import EventSubscriber
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository, ensure_translations_seeded
from app.worker.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)
        translations_repository = await startup_container.get(TranslationsRepository)
        settings_repository = await startup_container.get(SettingsRepository)
        uow = await startup_container.get(UnitOfWork)
        async with uow:
            await ensure_translations_seeded(config, translations_repository, settings_repository)

    event_subscriber = await container.get(EventSubscriber)
    event_subscriber.autodiscover()

    yield

    await event_subscriber.shutdown()
    await broker.shutdown()
    await container.close()
