from typing import Final

_GMAIL_DOMAINS: Final[frozenset[str]] = frozenset({"gmail.com", "googlemail.com"})
_YANDEX_DOMAINS: Final[frozenset[str]] = frozenset(
    {"yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz", "yandex.ua"}
)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def canonical_email(value: str) -> str:
    # one mailbox, one key: provider aliases fold into the address mail actually reaches
    normalized = normalize_email(value)
    local, sep, domain = normalized.rpartition("@")
    if not sep:
        return normalized
    local = local.split("+", 1)[0] or local
    if domain in _GMAIL_DOMAINS:
        return f"{local.replace('.', '')}@gmail.com"
    if domain in _YANDEX_DOMAINS:
        return f"{local.replace('-', '.')}@yandex.ru"
    return f"{local}@{domain}"
