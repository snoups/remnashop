from app.core.constants import CABINET_OAUTH_PROVIDERS
from app.modules.users.dto import UserDto
from app.modules.users.ports import OAuthIdentityLookup


async def customer_sign_in_ids(
    admins: list[UserDto], oauth_identity_lookup: OAuthIdentityLookup
) -> frozenset[int]:
    """Staff who can still sign in once demoted: demoting clears the login."""
    # GitHub/OIDC open only the dashboard, gone with the login
    with_oauth = await oauth_identity_lookup.user_ids_with_identities(
        [admin.id for admin in admins], CABINET_OAUTH_PROVIDERS
    )
    return frozenset(
        admin.id
        for admin in admins
        if admin.telegram_id is not None or admin.email is not None or admin.id in with_oauth
    )
