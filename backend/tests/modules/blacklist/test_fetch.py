from app.modules.blacklist.fetch import parse_source_text


def test_parses_bare_ids():
    text = "123\n456\n\n789\n"
    parsed = parse_source_text(text)
    assert parsed.telegram_ids == [123, 456, 789]
    assert parsed.emails == []


def test_parses_id_with_trailing_comment():
    text = "7021477105 # @scammer, reselling\n8899001122#note\n"
    parsed = parse_source_text(text)
    assert parsed.telegram_ids == [7021477105, 8899001122]


def test_skips_comment_and_header_lines():
    text = "# Community blacklist v3\n# maintained by ...\n555\n"
    parsed = parse_source_text(text)
    assert parsed.telegram_ids == [555]


def test_parses_mixed_ids_and_emails():
    text = "123\nbad@example.com\nAlso@Bad.com # chargebacks\n"
    parsed = parse_source_text(text)
    assert parsed.telegram_ids == [123]
    assert parsed.emails == ["also@bad.com", "bad@example.com"]


def test_digit_bearing_emails_are_not_parsed_as_telegram_ids():
    text = "support1234567890@example.com\n123\nuser99@gmail.com # chargebacks\n"
    parsed = parse_source_text(text)
    assert parsed.emails == ["support1234567890@example.com", "user99@gmail.com"]
    assert parsed.telegram_ids == [123]


def test_dedupes_and_sorts():
    text = "5\n3\n5\n"
    parsed = parse_source_text(text)
    assert parsed.telegram_ids == [3, 5]
