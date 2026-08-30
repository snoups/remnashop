from typing import Final

# Client-declared content-type is not proof of what the file actually is --
# cross-check against the file's own magic bytes before trusting it. Keyed by
# lowercase extension so callers can pass any format enum's `.value` (e.g.
# BannerFormat, AppearanceImageFormat) without a shared enum type.
_MAGIC_BYTES_BY_EXTENSION: Final[dict[str, bytes]] = {
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
    "gif": b"GIF8",
}


def matches_image_magic_bytes(data: bytes, extension: str) -> bool:
    if extension == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    signature = _MAGIC_BYTES_BY_EXTENSION.get(extension)
    return signature is not None and data.startswith(signature)
