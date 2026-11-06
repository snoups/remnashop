import pytest

from app.core.utils.image import matches_image_magic_bytes, read_svg_size

FAKE_JPG = b"\xff\xd8\xff\xe0rest-of-file"
FAKE_PNG = b"\x89PNG\r\n\x1a\nrest-of-file"
FAKE_GIF = b"GIF89arest-of-file"
FAKE_WEBP = b"RIFF\x00\x00\x00\x00WEBPrest-of-file"


def test_matches_image_magic_bytes_jpg() -> None:
    assert matches_image_magic_bytes(FAKE_JPG, "jpg")


def test_matches_image_magic_bytes_png() -> None:
    assert matches_image_magic_bytes(FAKE_PNG, "png")


def test_matches_image_magic_bytes_gif() -> None:
    assert matches_image_magic_bytes(FAKE_GIF, "gif")


def test_matches_image_magic_bytes_webp() -> None:
    assert matches_image_magic_bytes(FAKE_WEBP, "webp")


def test_matches_image_magic_bytes_rejects_mismatched_content() -> None:
    assert not matches_image_magic_bytes(FAKE_PNG, "jpg")


def test_matches_image_magic_bytes_rejects_unknown_extension() -> None:
    assert not matches_image_magic_bytes(FAKE_PNG, "svg")


_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 20"></svg>'
_BOMB = '<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg"/>'


def test_a_plain_utf8_svg_is_read() -> None:
    assert read_svg_size(_SVG.encode()) == (10.0, 20.0)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_an_svg_in_utf16_is_refused(encoding: str) -> None:
    # the DOCTYPE check reads bytes: in UTF-16 it would miss the entities
    assert read_svg_size(_BOMB.encode(encoding)) is None
    assert read_svg_size(_SVG.encode(encoding)) is None
