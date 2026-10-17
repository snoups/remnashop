from dishka.integrations.taskiq import FromDishka, inject

from app.core.broker import broker
from app.core.enums import AdLinkChannel
from app.modules.advertising.dto import RecordAdLinkAttributionDto
from app.modules.advertising.usecases import RecordAdLinkAttributionUseCase


@broker.task
@inject(patch_module=True)
async def record_ad_link_attribution_task(
    user_id: int,
    ad_link_code: str,
    channel: str,
    use_case: FromDishka[RecordAdLinkAttributionUseCase],
) -> None:
    await use_case.system(
        RecordAdLinkAttributionDto(
            user_id=user_id, ad_link_code=ad_link_code, channel=AdLinkChannel(channel)
        )
    )
