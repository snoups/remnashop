from app.core.utils.image import matches_image_magic_bytes

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
