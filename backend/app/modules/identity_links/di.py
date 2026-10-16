from dishka import Provider, Scope, provide, provide_all

from app.modules.identity_links.email_codes import LinkEmailCodeStore
from app.modules.identity_links.linker import IdentityLinker
from app.modules.identity_links.merge_tokens import MergeTokenStore
from app.modules.identity_links.usecases import (
    ConfirmMergeUseCase,
    ListIdentitiesUseCase,
    OAuthLinkAuthorizeUseCase,
    OAuthLinkCallbackUseCase,
    RequestLinkEmailCodeUseCase,
    RequestTelegramLinkUseCase,
    TelegramLinkSignInUseCase,
    UnlinkIdentityUseCase,
    VerifyLinkEmailCodeUseCase,
)


class IdentityLinksProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        ConfirmMergeUseCase,
        ListIdentitiesUseCase,
        OAuthLinkAuthorizeUseCase,
        OAuthLinkCallbackUseCase,
        RequestLinkEmailCodeUseCase,
        RequestTelegramLinkUseCase,
        TelegramLinkSignInUseCase,
        UnlinkIdentityUseCase,
        VerifyLinkEmailCodeUseCase,
    )
    linker = provide(IdentityLinker)
    email_code_store = provide(LinkEmailCodeStore)
    merge_tokens = provide(MergeTokenStore)


def get_identity_links_providers() -> list[Provider]:
    return [IdentityLinksProvider()]
