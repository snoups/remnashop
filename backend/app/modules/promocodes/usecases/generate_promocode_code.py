import secrets
import string
from typing import Final

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto

_CODE_ALPHABET: Final[str] = string.ascii_uppercase + string.digits
_CODE_LENGTH: Final[int] = 10


class GeneratePromocodeCodeUseCase(UseCase[None, str]):
    required_permission = Permission.PROMOCODES_GENERATE_CODE

    def __init__(self, promocode_repository: PromocodeRepository) -> None:
        self._promocode_repository = promocode_repository

    async def _execute(self, actor: UserDto, data: None) -> str:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if await self._promocode_repository.get_by_code(code) is None:
                return code
