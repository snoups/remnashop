import httpx
from loguru import logger
from pydantic import ValidationError
from remnapy import RemnawaveSDK
from remnapy.exceptions import ApiError
from remnapy.models.hwid import PlatformStatItem

from app.core.actor import Actor
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.overview.dto import AppCountDto, ClientAppsDto, PlatformAppsDto


def _platforms(stats: list[PlatformStatItem]) -> list[PlatformAppsDto]:
    platforms = [
        PlatformAppsDto(
            platform=p.platform,
            total=int(p.count),
            apps=sorted(
                (AppCountDto(app=a.app, count=int(a.count)) for a in p.by_app),
                key=lambda a: -a.count,
            ),
        )
        for p in stats
    ]
    return sorted(platforms, key=lambda p: -p.total)


class GetClientAppsUseCase(UseCase[None, ClientAppsDto]):
    required_permission = Permission.REMNAWAVE_CLIENT_APPS_VIEW

    def __init__(self, remnawave_sdk: RemnawaveSDK) -> None:
        self._remnawave_sdk = remnawave_sdk

    async def _execute(self, actor: Actor, data: None) -> ClientAppsDto:
        try:
            stats = await self._remnawave_sdk.hwid.get_hwid_stats()
        except (
            RemnawavePanelUnavailableError,
            ApiError,
            ValidationError,
            httpx.HTTPError,
        ) as error:
            logger.warning(f"Remnawave response unusable: {type(error).__name__}")
            return ClientAppsDto(
                available=False, total_devices=0, average_per_user=0.0, platforms=[]
            )
        return ClientAppsDto(
            available=True,
            total_devices=int(stats.stats.total_unique_devices),
            average_per_user=stats.stats.average_hwid_devices_per_user,
            platforms=_platforms(stats.by_platform),
        )
