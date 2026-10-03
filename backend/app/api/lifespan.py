import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from prometheus_client import REGISTRY
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.metrics import register_db_pool_metrics
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.modules.banners import BannerRepository, ensure_default_banner_seeded
from app.modules.blacklist import BlacklistRepository, ensure_blacklist_sources_seeded
from app.modules.dialogs import DialogRepository, ensure_dialogs_seeded, register_all_flow_metadata
from app.modules.translations import TranslationRepository, ensure_translations_seeded
from app.modules.users import UserRepository
from app.worker.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container
    engine = await container.get(AsyncEngine)
    register_db_pool_metrics(engine, registry=REGISTRY)

    redis = await container.get(Redis)
    runtime_heartbeat_task = asyncio.create_task(poll_runtime_heartbeat(redis, "api"))

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)
        translation_repository = await startup_container.get(TranslationRepository)
        uow = await startup_container.get(UnitOfWork)
        async with uow:
            register_all_flow_metadata()
            await ensure_translations_seeded(config, translation_repository)

            # fresh install only: once an owner exists the list is theirs, and
            # a source they removed must stay removed
            user_repository = await startup_container.get(UserRepository)
            if not await user_repository.exists_with_role(Role.OWNER):
                blacklist_repository = await startup_container.get(BlacklistRepository)
                await ensure_blacklist_sources_seeded(blacklist_repository)

            banner_repository = await startup_container.get(BannerRepository)
            await ensure_default_banner_seeded(banner_repository, config)

            dialog_repository = await startup_container.get(DialogRepository)
            await ensure_dialogs_seeded(dialog_repository, translation_repository)

    yield

    runtime_heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runtime_heartbeat_task
    await broker.shutdown()
    await container.close()
