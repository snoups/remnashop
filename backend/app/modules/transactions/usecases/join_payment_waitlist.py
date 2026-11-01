from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.transactions.waitlist_repository import WaitlistRepository
from app.modules.users import UserDto


class JoinPaymentWaitlistUseCase(UseCase[None, None, UserDto]):
    # the cabinet's "notify me" while payments are off; with them on there is nothing to wait for
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        get_access_settings_use_case: GetAccessSettingsUseCase,
        waitlist_repository: WaitlistRepository,
        uow: UnitOfWork,
    ) -> None:
        self._get_access_settings_use_case = get_access_settings_use_case
        self._waitlist_repository = waitlist_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> None:
        if (await self._get_access_settings_use_case.system()).payments_enabled:
            return
        async with self._uow:
            await self._waitlist_repository.add(actor.id)
