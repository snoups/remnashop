from app.core.constants import DOMAIN_REGEX
from app.core.enums import Locale


def is_valid_domain(text: str) -> bool:
    return bool(DOMAIN_REGEX.match(text))


def known_locale(value: object) -> object:
    # a stale client may send a language we no longer have; the request must still work
    try:
        return Locale(str(value))
    except ValueError:
        return None
