from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import PromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto


class ListPromocodesUseCase(UseCase[None, list[PromocodeDto]]):
    required_permission = Permission.PROMOCODES_VIEW

    def __init__(self, promocode_repository: PromocodeRepository) -> None:
        self._promocode_repository = promocode_repository

    async def _execute(self, actor: UserDto, data: None) -> list[PromocodeDto]:
        return await self._promocode_repository.list_all()
