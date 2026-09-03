from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users import UserDto


class DeleteAdLinkUseCase(UseCase[int, None]):
    required_permission = Permission.AD_LINKS_DELETE

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        if await self._ad_link_repository.has_attributions(data):
            raise ValidationError(
                f"AdLink '{data}' has attributions and cannot be deleted -- deactivate it instead"
            )
        async with self._uow:
            await self._ad_link_repository.delete(data)
        logger.info(f"{actor.log} Deleted ad link '{data}'")
