from app.core.constants import REDIS_KEY_PREFIX
from app.modules.cabinet_auth import EmailCodeStore


# its own key space: a login code must never confirm a link, nor the other way round
class LinkEmailCodeStore(EmailCodeStore):
    key_prefix = f"{REDIS_KEY_PREFIX}identity:email_code:"


def link_fail_key(user_id: int, digest: str) -> str:
    """The daily failure budget of one customer linking one mailbox: kept apart
    from sign-in's, so failed links can't lock the mailbox owner out of sign-in."""
    return f"link:{user_id}:{digest}"
