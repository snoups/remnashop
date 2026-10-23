from typing import Final

_GMAIL_DOMAINS: Final[frozenset[str]] = frozenset({"gmail.com", "googlemail.com"})
_YANDEX_DOMAINS: Final[frozenset[str]] = frozenset(
    {"yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz", "yandex.ua"}
)
_ICLOUD_DOMAINS: Final[frozenset[str]] = frozenset({"icloud.com", "me.com", "mac.com"})


def normalize_email(value: str) -> str:
    return value.strip().lower()


def alias_domains(domain: str) -> frozenset[str]:
    # every domain whose addresses canonical_email can fold into this one's
    for group in (_GMAIL_DOMAINS, _YANDEX_DOMAINS, _ICLOUD_DOMAINS):
        if domain in group:
            return group
    return frozenset({domain})


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
    if domain in _ICLOUD_DOMAINS:
        return f"{local}@icloud.com"
    return f"{local}@{domain}"
