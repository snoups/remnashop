from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.ports import BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners import BannerRepository
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._banners import drop_window_banners


class DeleteCustomDialogWindowUseCase(UseCase[str, None]):
    required_permission = Permission.DIALOGS_WINDOWS_DELETE

    def __init__(
        self,
        dialog_repository: DialogRepository,
        banner_repository: BannerRepository,
        config: AppConfig,
        uow: UnitOfWork,
        bot_signals: BotSignals,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow
        self._bot_signals = bot_signals

    async def _execute(self, actor: Actor, data: str) -> None:
        async with self._uow:
            await self._dialog_repository.delete_custom_window(data)
            await drop_window_banners(self._banner_repository, self._config, data)
        await self._bot_signals.dialogs_changed()
