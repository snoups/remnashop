from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import AudiencePreviewDto, PreviewAudienceDto
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.validation import validate_audience


class PreviewBroadcastAudienceUseCase(UseCase[PreviewAudienceDto, AudiencePreviewDto]):
    required_permission = Permission.BROADCASTS_AUDIENCE_PREVIEW

    def __init__(self, broadcast_repository: BroadcastRepository, uow: UnitOfWork) -> None:
        self._broadcast_repository = broadcast_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: PreviewAudienceDto) -> AudiencePreviewDto:
        validate_audience(data.audience)
        async with self._uow:
            by_locale = await self._broadcast_repository.count_audience(
                data.audience, data.category, datetime_now()
            )
        return AudiencePreviewDto(total=sum(by_locale.values()), by_locale=by_locale)
