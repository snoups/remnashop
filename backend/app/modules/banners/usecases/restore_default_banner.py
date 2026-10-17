from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import DEFAULT_BANNER_NAME
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerDto
from app.modules.banners.events import BannerChangedEvent
from app.modules.banners.repository import BannerRepository
from app.modules.banners.seed import restore_default_banner
from app.modules.translations import TranslationRepository


class RestoreDefaultBannerUseCase(UseCase[None, BannerDto]):
    """Puts the picture shipped with the project back as the shared banner."""

    required_permission = Permission.BANNERS_RESTORE_DEFAULT

    def __init__(
        self,
        banner_repository: BannerRepository,
        translation_repository: TranslationRepository,
        config: AppConfig,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._banner_repository = banner_repository
        self._translation_repository = translation_repository
        self._config = config
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> BannerDto:
        async with self._uow:
            default_locale = await self._translation_repository.get_default_locale()
            banner = await restore_default_banner(
                self._banner_repository, self._config, default_locale
            )
            await self._event_publisher.publish(
                BannerChangedEvent(actor=actor, action="reset_default", name=DEFAULT_BANNER_NAME)
            )
        return banner
