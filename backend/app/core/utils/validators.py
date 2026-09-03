from app.core.constants import DOMAIN_REGEX


def is_valid_domain(text: str) -> bool:
    return bool(DOMAIN_REGEX.match(text))
