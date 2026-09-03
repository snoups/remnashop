import secrets
import string
from typing import Final

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users import UserDto

_CODE_ALPHABET: Final[str] = string.ascii_letters + string.digits
_CODE_LENGTH: Final[int] = 12


class GenerateAdLinkCodeUseCase(UseCase[None, str]):
    required_permission = Permission.AD_LINKS_GENERATE_CODE

    def __init__(self, ad_link_repository: AdLinkRepository) -> None:
        self._ad_link_repository = ad_link_repository

    async def _execute(self, actor: UserDto, data: None) -> str:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if await self._ad_link_repository.get_by_code(code) is None:
                return code
