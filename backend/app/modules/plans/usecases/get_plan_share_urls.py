from typing import Final, Optional

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import PLAN_START_PREFIX, T_ME
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanShareUrlsDto
from app.modules.plans.repository import PlanRepository
from app.modules.settings import SettingsRepository, fetch_bot_username

_WEBCABINET_PATH: Final[str] = "purchase?plan={code}"


class GetPlanShareUrlsUseCase(UseCase[int, PlanShareUrlsDto]):
    required_permission = Permission.PLANS_SHARE_VIEW

    def __init__(
        self,
        plan_repository: PlanRepository,
        settings_repository: SettingsRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> PlanShareUrlsDto:
        async with self._uow:
            plan = await self._plan_repository.get_by_id(data)
            bot_settings = await self._settings_repository.get_bot_settings()

        bot_url: Optional[str] = None
        if bot_settings.is_configured and bot_settings.token is not None:
            username = await fetch_bot_username(
                bot_settings.token.get_secret_value(), bot_settings.proxy
            )
            if username:
                bot_url = f"{T_ME}{username}?start={PLAN_START_PREFIX}{plan.public_code}"

        webcabinet_url: Optional[str] = None
        cabinet_url = self._config.web_cabinet_url.strip().rstrip("/")
        if cabinet_url:
            webcabinet_url = f"{cabinet_url}/{_WEBCABINET_PATH.format(code=plan.public_code)}"

        return PlanShareUrlsDto(bot_url=bot_url, webcabinet_url=webcabinet_url)
