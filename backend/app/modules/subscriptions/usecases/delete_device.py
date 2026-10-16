from datetime import timedelta

from remnapy import RemnawaveSDK
from remnapy.models import DeleteUserHwidDeviceRequestDto

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.dto import DeleteDeviceDto
from app.modules.subscriptions.eligibility import get_owned_live_target
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class DeleteDeviceUseCase(UseCase[DeleteDeviceDto, None, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: DeleteDeviceDto) -> None:
        async with self._uow:
            shop_settings = await self._settings_repository.get_shop_settings()
            if not shop_settings.device_single_reset_enabled:
                raise ValidationError(
                    "Single device reset is disabled", code=ErrorCode.DEVICE_RESET_DISABLED
                )

            subscription = await get_owned_live_target(
                self._subscription_repository, data.subscription_id, actor.id
            )

            previous = await self._subscription_repository.claim_reset(
                subscription.id,
                "device_single_reset_at",
                timedelta(hours=shop_settings.device_single_reset_cooldown_hours),
            )

        try:
            await self._remnawave_sdk.hwid.delete_hwid_to_user(
                DeleteUserHwidDeviceRequestDto(
                    user_id=subscription.remnawave_user_id, hwid=data.hwid
                )
            )
        except Exception:
            async with self._uow:
                await self._subscription_repository.set_reset_at(
                    subscription.id, "device_single_reset_at", previous
                )
            raise
