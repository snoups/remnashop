from app.core.utils.telegram_text import PREMIUM_EMOJI_RE, telegram_length


def test_premium_emoji_markup_counts_as_its_glyph() -> None:
    markup = "[😀](emoji:5368324170671202286) hi"
    expected_length = len("😀 hi".encode("utf-16-le")) // 2
    assert telegram_length(markup) == expected_length


def test_astral_emoji_counts_two_units() -> None:
    assert telegram_length("😀") == 2


def test_regex_captures_glyph_and_id() -> None:
    match = PREMIUM_EMOJI_RE.search("[🔥](emoji:42)")
    assert match is not None and match.groups() == ("🔥", "42")
