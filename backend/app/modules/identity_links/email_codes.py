from app.core.constants import REDIS_KEY_PREFIX
from app.modules.cabinet_auth import EmailCodeStore


# its own key space: a login code must never confirm a link, nor the other way round
class LinkEmailCodeStore(EmailCodeStore):
    key_prefix = f"{REDIS_KEY_PREFIX}identity:email_code:"
