from types import SimpleNamespace
from typing import Optional, cast

import httpx
import pytest
from pydantic import ValidationError
from remnapy import RemnawaveSDK
from remnapy.models import GetHwidStatisticsResponseDto

from app.core.enums import Locale, Role
from app.core.exceptions import PermissionDeniedError, RemnawavePanelUnavailableError
from app.modules.overview.usecases import GetClientAppsUseCase
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


class _HwidStub:
    def __init__(
        self,
        stats: Optional[GetHwidStatisticsResponseDto] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self._stats, self._error = stats, error

    async def get_hwid_stats(self) -> Optional[GetHwidStatisticsResponseDto]:
        if self._error is not None:
            raise self._error
        return self._stats


def _sdk(stub: _HwidStub) -> RemnawaveSDK:
    return cast(RemnawaveSDK, SimpleNamespace(hwid=stub))


_STATS = GetHwidStatisticsResponseDto.model_validate(
    {
        "byPlatform": [
            {"platform": "ios", "count": 3.0, "byApp": [{"app": "Streisand", "count": 3.0}]},
            {
                "platform": "android",
                "count": 10.0,
                "byApp": [{"app": "Happ", "count": 4.0}, {"app": "v2rayTun", "count": 6.0}],
            },
        ],
        "stats": {
            "totalUniqueDevices": 13.0,
            "totalHwidDevices": 14.0,
            "averageHwidDevicesPerUser": 1.5,
        },
    }
)


async def test_orders_platforms_and_apps_by_count() -> None:
    result = await GetClientAppsUseCase(_sdk(_HwidStub(_STATS)))(OWNER)

    assert result.available is True
    assert result.total_devices == 13
    assert result.average_per_user == 1.5
    assert [p.platform for p in result.platforms] == ["android", "ios"]
    assert result.platforms[0].total == 10
    assert [(a.app, a.count) for a in result.platforms[0].apps] == [("v2rayTun", 6), ("Happ", 4)]


async def test_unavailable_panel_is_reported_not_raised() -> None:
    sdk = _sdk(_HwidStub(error=RemnawavePanelUnavailableError("down")))

    result = await GetClientAppsUseCase(sdk)(OWNER)

    assert result.available is False
    assert (result.total_devices, result.average_per_user, result.platforms) == (0, 0.0, [])


async def test_requires_the_client_apps_permission() -> None:
    actor = OWNER.model_copy(update={"permission_revokes": ["REMNAWAVE_CLIENT_APPS_VIEW"]})

    with pytest.raises(PermissionDeniedError):
        await GetClientAppsUseCase(_sdk(_HwidStub(_STATS)))(actor)


async def test_unparsable_panel_response_is_reported_not_raised() -> None:
    error = ValidationError.from_exception_data("X", [])

    result = await GetClientAppsUseCase(_sdk(_HwidStub(error=error)))(OWNER)

    assert result.available is False


async def test_transport_error_before_the_breaker_opens_marks_the_card_unavailable() -> None:
    sdk = _sdk(_HwidStub(error=httpx.ConnectError("down")))

    result = await GetClientAppsUseCase(sdk)(OWNER)

    assert result.available is False
