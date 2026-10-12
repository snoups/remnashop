from collections.abc import Iterable
from typing import Final

DISPOSABLE_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "mailinator.com",
        "10minutemail.com",
        "10minutemail.net",
        "guerrillamail.com",
        "guerrillamail.net",
        "guerrillamail.org",
        "guerrillamail.biz",
        "guerrillamail.de",
        "grr.la",
        "sharklasers.com",
        "temp-mail.org",
        "temp-mail.io",
        "tempmail.com",
        "tempmail.net",
        "tempail.com",
        "yopmail.com",
        "yopmail.net",
        "yopmail.fr",
        "trashmail.com",
        "trashmail.net",
        "trashmail.de",
        "throwawaymail.com",
        "getnada.com",
        "nada.email",
        "dispostable.com",
        "maildrop.cc",
        "mailnesia.com",
        "mailcatch.com",
        "mintemail.com",
        "mytemp.email",
        "fakeinbox.com",
        "fakemail.net",
        "emailondeck.com",
        "spamgourmet.com",
        "spambox.us",
        "mohmal.com",
        "burnermail.io",
        "moakt.com",
        "tmail.ws",
        "tmpmail.org",
        "tmpmail.net",
        "discard.email",
        "mailtemp.net",
        "mail-temp.com",
        "emailfake.com",
        "crazymailing.com",
        "inboxkitten.com",
        "harakirimail.com",
        "33mail.com",
        "anonbox.net",
        "tempinbox.com",
        "temporary-mail.net",
        "owlymail.com",
        "mailforspam.com",
    }
)


def is_disposable(email: str, extra: Iterable[str]) -> bool:
    domain = email.rsplit("@", 1)[-1].strip().lower()
    blocked = DISPOSABLE_DOMAINS.union(extra)
    labels = domain.split(".")
    return any(".".join(labels[i:]) in blocked for i in range(len(labels)))
