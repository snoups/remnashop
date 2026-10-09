import asyncio

import httpx
import pytest

from app.modules.blacklist import fetch
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


async def test_fetch_source_gives_up_on_a_source_that_trickles_bytes(monkeypatch) -> None:
    class _Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:  # each read is quick, the response never ends
                await asyncio.sleep(0.01)
                yield b"1"

    real_client = httpx.AsyncClient

    def _client(**kwargs):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=_Trickle()))
        return real_client(transport=transport, **kwargs)

    async def _public(url: str) -> None:
        return None

    monkeypatch.setattr(fetch, "assert_public_https_host", _public)
    monkeypatch.setattr(fetch.httpx, "AsyncClient", _client)
    monkeypatch.setattr(fetch, "_DEADLINE_S", 0.1)

    with pytest.raises(ValueError, match="did not finish"):
        await fetch.fetch_source("https://blacklist.example/list.txt")


def test_takes_the_first_csv_field_and_skips_dates():
    parsed = parse_source_text("123456789,spam,2024-01-01\n2024-01-15\njohn99@gmail.com\n5;x\n")
    assert parsed.telegram_ids == [5, 123456789]
    assert parsed.emails == ["john99@gmail.com"]


async def test_fetch_source_reads_a_file_with_a_byte_order_mark(monkeypatch) -> None:
    async def _public(url: str) -> None:
        return None

    async def _download(url: str) -> bytes:
        return "\ufeff123\n456\n".encode()

    monkeypatch.setattr(fetch, "assert_public_https_host", _public)
    monkeypatch.setattr(fetch, "_download", _download)
    parsed = await fetch.fetch_source("https://feed.example/list.txt")
    assert parsed.telegram_ids == [123, 456]
