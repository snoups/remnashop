from typing import Optional

from app.core.enums import OAuthProvider
from app.modules.identity_links.dto import IdentityDto, IdentityKind, can_edit_identity
from app.modules.oauth import OAuthIdentityDto
from app.modules.settings import CabinetAuthSettingsDto
from app.modules.users import UserDto


def _telegram_label(user: UserDto) -> Optional[str]:
    if user.username:
        return f"@{user.username}"
    return str(user.telegram_id) if user.telegram_id is not None else None


def build_identities(
    user: UserDto, cabinet: CabinetAuthSettingsDto, oauth_identities: list[OAuthIdentityDto]
) -> list[IdentityDto]:
    linked = {identity.provider: identity for identity in oauth_identities}
    items = [
        IdentityDto(
            kind=IdentityKind.TELEGRAM,
            linked=user.telegram_id is not None,
            label=_telegram_label(user),
            editable=can_edit_identity(user, IdentityKind.TELEGRAM),
        ),
        IdentityDto(
            kind=IdentityKind.EMAIL,
            linked=user.email is not None,
            label=user.email,
            editable=can_edit_identity(user, IdentityKind.EMAIL),
        ),
    ]
    for kind, enabled in (
        (IdentityKind.GOOGLE, cabinet.google_enabled),
        (IdentityKind.YANDEX, cabinet.yandex_enabled),
    ):
        # a provider switched off later stays listed while linked, so it can be unlinked
        identity = linked.get(OAuthProvider(kind.value))
        if enabled or identity is not None:
            items.append(
                IdentityDto(
                    kind=kind,
                    linked=identity is not None,
                    label=identity.external_login or identity.external_id if identity else None,
                    editable=can_edit_identity(user, kind),
                )
            )
    return items
