from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.admin import require_admin_user
from app.api.errors import error_responses
from app.modules.email.usecases import SendTestEmailUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/settings/email", tags=["settings"])


@router.post(
    "/actions/test",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400),
)
@inject
async def send_test_email(
    use_case: FromDishka[SendTestEmailUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor)
