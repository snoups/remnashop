from dataclasses import dataclass
from datetime import timedelta

from remnapy import RemnawaveSDK
from remnapy.models import DeleteUserHwidDeviceRequestDto

from app.core.exceptions import CooldownError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class DeleteDeviceDto:
    hwid: str


class DeleteDeviceUseCase(UseCase[DeleteDeviceDto, None]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        settings_repository: SettingsRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._settings_repository = settings_repository

    async def _execute(self, actor: UserDto, data: DeleteDeviceDto) -> None:
        shop_settings = await self._settings_repository.get_shop_settings()
        if not shop_settings.device_single_reset_enabled:
            raise ValidationError("Single device reset is disabled")

        subscription = await self._subscription_repository.get_single_active_subscription_or_raise(
            actor.id
        )

        cooldown_hours = shop_settings.device_single_reset_cooldown_hours
        if cooldown_hours > 0 and subscription.device_single_reset_at is not None:
            available_at = subscription.device_single_reset_at + timedelta(hours=cooldown_hours)
            if datetime_now() < available_at:
                raise CooldownError(available_at)

        await self._remnawave_sdk.hwid.delete_hwid_to_user(
            DeleteUserHwidDeviceRequestDto(user_id=subscription.remnawave_user_id, hwid=data.hwid)
        )
        await self._subscription_repository.mark_device_single_reset(subscription.id)
