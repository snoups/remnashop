import pytest

from app.modules.users.display_name import MAX_NAME_LENGTH, clean_telegram_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Иван Петров", "Иван Петров"),
        ("O'Brien-Smith Jr.", "O'Brien-Smith Jr."),
        ("नमस्ते", "नमस्ते"),
        ("  lots   of\tspace ", "lots of space"),
        ("<b>Bold</b> &amp; co", "Bold co"),
        ("{ $name } -{ -brand }", "name - -brand"),
        ("[x](emoji:5368324170671202286) Eve", "xemoji5368324170671202286 Eve"),
        ("${user.name}", "user.name"),
        ("Bob https://t.me/spam", "Bob"),
        (chr(0x202E) + "evil" + chr(0x200D), "evil"),
        ("Ｆｕｌｌｗｉｄｔｈ", "Fullwidth"),
        ("😀 Anna 🔥", "Anna"),
    ],
)
def test_clean_telegram_name(raw: str, expected: str) -> None:
    assert clean_telegram_name(raw, 1) == expected


def test_clean_telegram_name_falls_back_to_the_telegram_id() -> None:
    assert clean_telegram_name("😀🔥", 42) == "42"
    assert clean_telegram_name(None, 42) == "42"


def test_clean_telegram_name_caps_the_length() -> None:
    assert len(clean_telegram_name("a" * 100, 1)) == MAX_NAME_LENGTH
