from typing import Optional

from app.core.enums import OAuthProvider
from app.modules.cabinet_auth import CabinetOAuthCallbackUseCase, telegram_profile_from_oauth
from app.modules.identity_links.dto import (
    IdentityClaimDto,
    IdentityKind,
    LinkResultDto,
    identity_kind_for,
)
from app.modules.identity_links.linker import IdentityLinker
from app.modules.users import UserDto


class OAuthLinkCallbackUseCase:
    def __init__(self, callback: CabinetOAuthCallbackUseCase, linker: IdentityLinker) -> None:
        self._callback = callback
        self._linker = linker

    async def execute(
        self,
        user: UserDto,
        provider: OAuthProvider,
        code: str,
        state: str,
        binding: Optional[str],
        client_ip: str,
    ) -> LinkResultDto:
        profile = await self._callback.fetch_profile(
            provider, code, state, binding, link_user_id=user.id
        )
        if provider is OAuthProvider.TELEGRAM:
            claim = IdentityClaimDto(
                kind=IdentityKind.TELEGRAM, telegram=telegram_profile_from_oauth(profile)
            )
        else:
            claim = IdentityClaimDto(kind=identity_kind_for(provider), oauth=profile)
        return await self._linker.link(user, claim, client_ip)
