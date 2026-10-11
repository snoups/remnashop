from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.public import get_cabinet_user
from app.core.constants import CABINET_API_PREFIX
from app.modules.cabinet_auth.api.schemas import CabinetProfileResponse
from app.modules.cabinet_auth.usecases import GetCabinetProfileUseCase
from app.modules.users import UserDto

router = APIRouter(prefix=CABINET_API_PREFIX, tags=["cabinet"])


@router.get("/me", response_model=CabinetProfileResponse)
@inject
async def get_cabinet_me(
    use_case: FromDishka[GetCabinetProfileUseCase],
    user: UserDto = Depends(get_cabinet_user),
) -> CabinetProfileResponse:
    profile = await use_case(user)
    return CabinetProfileResponse.model_validate(profile, from_attributes=True)
