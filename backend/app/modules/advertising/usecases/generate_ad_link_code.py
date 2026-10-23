import secrets
import string
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.repository import AdLinkRepository

_CODE_ALPHABET: Final[str] = string.ascii_letters + string.digits
_CODE_LENGTH: Final[int] = 12


class GenerateAdLinkCodeUseCase(UseCase[None, str]):
    required_permission = Permission.AD_LINKS_GENERATE_CODE

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> str:
        async with self._uow:
            while True:
                code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
                if await self._ad_link_repository.find_by_code(code) is None:
                    return code
