from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.http import assert_public_https_host
from app.modules.settings.dto import OAuthSettingsDto, UpdateOAuthSettingsDto
from app.modules.settings.events import OidcIssuerChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateOAuthSettingsUseCase(UseCase[UpdateOAuthSettingsDto, OAuthSettingsDto]):
    required_permission = Permission.OAUTH_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateOAuthSettingsDto) -> OAuthSettingsDto:
        if data.oidc_issuer_url is not None:
            await assert_public_https_host(data.oidc_issuer_url)

        async with self._uow:
            current = await self._settings_repository.get_oauth_settings()
            issuer_changed = (
                data.oidc_issuer_url is not None and data.oidc_issuer_url != current.oidc_issuer_url
            )

        async with self._uow:
            settings = await self._settings_repository.update_oauth_settings(data)
            if issuer_changed:
                # a new issuer's `sub` could collide with an old identity's and
                # log in as that user, so the old rows go
                await self._event_publisher.publish(OidcIssuerChangedEvent(actor=actor))
        return settings
