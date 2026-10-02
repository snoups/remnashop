from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status

from app.api.errors import ApiError, error_responses
from app.core.config import AppConfig
from app.core.constants import MAX_WEBHOOK_BODY_BYTES, REMNAWAVE_WEBHOOK_PATH
from app.core.error_codes import ErrorCode
from app.core.utils.http import read_bounded_body
from app.modules.subscriptions.dto import RemnawaveWebhookDto
from app.modules.subscriptions.usecases import HandleRemnawaveWebhookUseCase

router = APIRouter(tags=["subscriptions"])


@router.post(REMNAWAVE_WEBHOOK_PATH, responses=error_responses(400, 401, 503))
@inject
async def receive_remnawave_webhook(
    request: Request,
    use_case: FromDishka[HandleRemnawaveWebhookUseCase],
    config: FromDishka[AppConfig],
) -> Response:
    if config.remnawave.webhook_secret is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Remnawave webhook secret is not configured",
            code=ErrorCode.WEBHOOK_NOT_CONFIGURED,
        )
    body = await read_bounded_body(request, MAX_WEBHOOK_BODY_BYTES)
    await use_case.system(RemnawaveWebhookDto(body=body, headers=dict(request.headers)))
    return Response(status_code=status.HTTP_200_OK)
