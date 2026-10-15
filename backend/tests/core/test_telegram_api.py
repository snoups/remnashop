from app.core.telegram_api import bot_file_url, bot_method_url, retry_after_seconds


def test_urls_point_at_the_bot_api() -> None:
    assert bot_method_url("123:abc", "getMe") == "https://api.telegram.org/bot123:abc/getMe"
    assert (
        bot_file_url("123:abc", "a/b.webp") == "https://api.telegram.org/file/bot123:abc/a/b.webp"
    )


def test_retry_after_reads_the_parameters_and_falls_back() -> None:
    assert retry_after_seconds({"parameters": {"retry_after": 7}}) == 7.0
    assert retry_after_seconds({"parameters": {"retry_after": "x"}}) == 1.0
    assert retry_after_seconds({}) == 1.0
