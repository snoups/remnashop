import pytest

from app.modules.users.display_name import MAX_NAME_LENGTH, clean_display_name


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
def test_clean_display_name(raw: str, expected: str) -> None:
    assert clean_display_name(raw) == expected


def test_clean_display_name_is_empty_without_a_name() -> None:
    assert clean_display_name("😀🔥") == ""
    assert clean_display_name(None) == ""


@pytest.mark.parametrize("raw", [".", "-_-", "'", "🐈‍⬛ .", " . "])
def test_clean_display_name_drops_names_without_letters_or_digits(raw: str) -> None:
    assert clean_display_name(raw) == ""


def test_clean_display_name_caps_the_length() -> None:
    assert len(clean_display_name("a" * 100)) == MAX_NAME_LENGTH
