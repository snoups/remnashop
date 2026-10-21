from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerKeyDto
from app.modules.banners.events import BannerChangedEvent
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import delete_banner_file


class DeleteBannerUseCase(UseCase[BannerKeyDto, None]):
    required_permission = Permission.BANNERS_DELETE

    def __init__(
        self,
        banner_repository: BannerRepository,
        config: AppConfig,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: BannerKeyDto) -> None:
        async with self._uow:
            banner = await self._banner_repository.get(data.name, data.locale)
            if banner is None:
                raise NotFoundError(
                    f"Banner not found: {data.name}/{data.locale}", code=ErrorCode.BANNER_NOT_FOUND
                )

            await self._banner_repository.delete(data.name, data.locale)
            await self._event_publisher.publish(
                BannerChangedEvent(actor=actor, action="delete", name=data.name, locale=data.locale)
            )
        delete_banner_file(self._config.media_dir, data.name, data.locale, banner.extension)
