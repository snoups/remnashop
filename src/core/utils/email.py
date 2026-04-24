import re

_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+"
)


def is_valid_email(value: str) -> bool:
    s = value.strip()
    if not s or len(s) > 254:
        return False
    return bool(_EMAIL_PATTERN.fullmatch(s))
