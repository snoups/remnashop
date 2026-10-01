from datetime import timedelta

from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import CooldownError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.repository import SubscriptionRepository


class ReissueSubscriptionUseCase(UseCase[None, None]):
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

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            shop_settings = await self._settings_repository.get_shop_settings()
            if not shop_settings.link_reset_enabled:
                raise ValidationError(
                    "Subscription link reset is disabled", code=ErrorCode.LINK_RESET_DISABLED
                )

            subscription = (
                await self._subscription_repository.get_single_active_subscription_or_raise(
                    actor.id
                )
            )

            cooldown_hours = shop_settings.link_reset_cooldown_hours
            if cooldown_hours > 0 and subscription.link_reset_at is not None:
                available_at = subscription.link_reset_at + timedelta(hours=cooldown_hours)
                if datetime_now() < available_at:
                    raise CooldownError(available_at)

        panel_user = await self._remnawave_sdk.users.revoke_user_subscription(
            subscription.remnawave_user_id
        )
        async with self._uow:
            await self._subscription_repository.mark_link_reset(
                subscription.id, new_url=panel_user.subscription_url
            )
