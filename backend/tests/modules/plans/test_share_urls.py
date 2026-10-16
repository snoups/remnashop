from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import PlanType
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import GetPlanShareUrlsUseCase
from app.modules.plans.usecases import get_plan_share_urls as module


class _Settings:
    def __init__(self, token: Optional[str]) -> None:
        self._token = token

    async def get_bot_settings(self) -> Any:
        return MagicMock(
            is_configured=self._token is not None,
            token=SecretStr(self._token) if self._token else None,
            proxy=None,
        )


async def _plan(plan_repository: PlanRepository) -> int:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="Ab12Cd34", name="P", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )
    return plan.id


async def test_links_open_the_plan_in_the_bot_and_the_cabinet(
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def username(token: str, proxy: object) -> str:
        return "shop_bot"

    monkeypatch.setattr(module, "fetch_bot_username", username)
    monkeypatch.setattr(config, "web_cabinet_url", "https://cabinet.example.com/")
    plan_id = await _plan(plan_repository)
    use_case = GetPlanShareUrlsUseCase(plan_repository, _Settings("t"), config, uow)  # type: ignore[arg-type]

    urls = await use_case.system(plan_id)

    assert urls.bot_url == "https://t.me/shop_bot?start=plan_Ab12Cd34"
    assert urls.webcabinet_url == "https://cabinet.example.com/purchase?plan=Ab12Cd34"


async def test_no_bot_and_no_cabinet_give_no_links(
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", "")
    plan_id = await _plan(plan_repository)
    use_case = GetPlanShareUrlsUseCase(plan_repository, _Settings(None), config, uow)  # type: ignore[arg-type]

    urls = await use_case.system(plan_id)

    assert (urls.bot_url, urls.webcabinet_url) == (None, None)
