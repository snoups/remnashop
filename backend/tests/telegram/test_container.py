from typing import Any, cast

from aiogram import Bot
from aiogram_dialog import BgManagerFactory
from dishka import Scope
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.modules.banners import BannerRepository
from app.modules.promocodes import ActivatePromocodeUseCase, ValidatePromocodeUseCase
from app.modules.subscriptions import (
    ActivateTrialSubscriptionUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    GetAvailableTrialUseCase,
    ListDevicesUseCase,
    ReissueSubscriptionUseCase,
    SubscriptionRepository,
)
from app.telegram.container import create_aiogram_container
from app.telegram.dialogs.config_cache import DialogConfigCache


async def test_aiogram_container_resolves_handler_dependencies(config: AppConfig) -> None:
    # make_async_container validates every provide()-registered factory's
    # dependency graph, so a missing provider here is a telegram process that
    # crashes on startup the moment a bot token is configured.
    placeholder = cast(Any, object())
    container = create_aiogram_container(
        config,
        cast(BgManagerFactory, placeholder),
        cast(Bot, placeholder),
        cast(TranslatorHub, placeholder),
    )
    # Handlers' FromDishka params aren't part of that build-time validation.
    async with container(scope=Scope.REQUEST) as request_container:
        for dependency in (
            ActivatePromocodeUseCase,
            ValidatePromocodeUseCase,
            ActivateTrialSubscriptionUseCase,
            DeleteAllDevicesUseCase,
            DeleteDeviceUseCase,
            GetAvailableTrialUseCase,
            ListDevicesUseCase,
            ReissueSubscriptionUseCase,
            SubscriptionRepository,
            BannerRepository,
            DialogConfigCache,
        ):
            await request_container.get(dependency)
    await container.close()
