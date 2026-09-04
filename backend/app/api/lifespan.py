from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.metrics import register_db_pool_metrics
from app.modules.dialogs import DialogRepository, ensure_dialogs_seeded
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository, ensure_translations_seeded
from app.worker.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container
    engine = await container.get(AsyncEngine)
    register_db_pool_metrics(engine, registry=REGISTRY)

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)
        translations_repository = await startup_container.get(TranslationsRepository)
        settings_repository = await startup_container.get(SettingsRepository)
        uow = await startup_container.get(UnitOfWork)
        async with uow:
            await ensure_translations_seeded(config, translations_repository, settings_repository)

            dialog_repository = await startup_container.get(DialogRepository)
            await ensure_dialogs_seeded(
                dialog_repository, translations_repository, settings_repository
            )

    yield

    await broker.shutdown()
    await container.close()
