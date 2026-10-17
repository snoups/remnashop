import re
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Final, Optional

from PIL import Image, UnidentifiedImageError

# The declared content type proves nothing; the magic bytes are checked too.
# Keyed by lowercase extension, so any format enum's `.value` (BannerFormat,
# AppearanceImageFormat) works without a shared enum type.

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


# Reads only the header, no pixel decode, so the caller's dimension check
# rejects a decompression bomb before anything big is allocated.
def read_image_size(data: bytes) -> Optional[tuple[int, int]]:
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        return None
    return width, height


_SVG_ROOT_TAG: Final[str] = "{http://www.w3.org/2000/svg}svg"
_FORBIDDEN_SVG_TAGS: Final[frozenset[str]] = frozenset({"script", "foreignobject"})
_SVG_LENGTH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(px)?\s*$")


def _local_name(qualified: str) -> str:
    return qualified.rsplit("}", 1)[-1].lower()


def _parse_svg_length(value: Optional[str]) -> Optional[float]:
    match = _SVG_LENGTH_PATTERN.match(value or "")
    return float(match.group(1)) if match else None


def _has_script_surface(root: ET.Element) -> bool:
    for element in root.iter():
        if _local_name(element.tag) in _FORBIDDEN_SVG_TAGS:
            return True
        for name, value in element.attrib.items():
            if _local_name(name).startswith("on") or value.strip().lower().startswith(
                "javascript:"
            ):
                return True
    return False


def _svg_dimensions(root: ET.Element) -> Optional[tuple[float, float]]:
    view_box = (root.get("viewBox") or "").replace(",", " ").split()
    if len(view_box) == 4:
        try:
            return float(view_box[2]), float(view_box[3])
        except ValueError:
            return None
    width = _parse_svg_length(root.get("width"))
    height = _parse_svg_length(root.get("height"))
    if width is None or height is None:
        return None
    return width, height


# None unless the SVG is plain markup: no DOCTYPE/entities (expansion bombs),
# no script-capable elements, event handlers or javascript: links. Size comes
# from viewBox, falling back to width/height.
def read_svg_size(data: bytes) -> Optional[tuple[float, float]]:
    lowered = data.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        return None
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    if root.tag != _SVG_ROOT_TAG or _has_script_surface(root):
        return None
    size = _svg_dimensions(root)
    if size is None or size[0] <= 0 or size[1] <= 0:
        return None
    return size
