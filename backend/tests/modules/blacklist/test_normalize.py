import pytest

from app.core.enums import BlacklistKind
from app.modules.blacklist.normalize import derive_source_name, normalize_identity

TG = BlacklistKind.TELEGRAM_ID
EMAIL = BlacklistKind.EMAIL


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("123456789", "123456789"),
        ("  123456789 ", "123456789"),
        ("id123456789", "123456789"),
        ("tg://user?id=123456789", "123456789"),
        ("-100123456789", "100123456789"),
        ("007", "7"),
        ("0", None),
        ("", None),
        ("not-a-number", None),
        ("x" * 300, None),
    ],
)
def test_normalize_telegram_id(raw: str, expected):
    assert normalize_identity(TG, raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("User@Example.com", "user@example.com"),
        ("  a@b.co  ", "a@b.co"),
        ("plainstring", None),
        ("no@spaces here@x", None),
        ("@nodomain", None),
        ("", None),
    ],
)
def test_normalize_email(raw: str, expected):
    assert normalize_identity(EMAIL, raw) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://raw.githubusercontent.com/remnashop/blacklist/main/blacklist.txt",
            "remnashop/blacklist",
        ),
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://www.example.com/lists/abuse.txt", "example.com/abuse.txt"),
        ("https://example.com", "example.com"),
        ("https://github.com/owner", "github.com/owner"),
    ],
)
def test_derive_source_name(url: str, expected: str) -> None:
    assert derive_source_name(url) == expected
