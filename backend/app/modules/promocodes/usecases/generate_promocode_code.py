import secrets
import string
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.repository import PromocodeRepository

_CODE_ALPHABET: Final[str] = string.ascii_uppercase + string.digits
_CODE_LENGTH: Final[int] = 10


class GeneratePromocodeCodeUseCase(UseCase[None, str]):
    required_permission = Permission.PROMOCODES_GENERATE_CODE

    def __init__(self, promocode_repository: PromocodeRepository, uow: UnitOfWork) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> str:
        async with self._uow:
            while True:
                code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
                if await self._promocode_repository.find_by_code(code) is None:
                    return code
