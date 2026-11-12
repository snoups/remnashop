import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final, Iterator, Optional

# moov holds only headers and sample tables; a bigger one isn't something we'd parse
_MAX_MOOV_BYTES: Final[int] = 16 * 1024 * 1024


@dataclass(frozen=True, kw_only=True)
class VideoMeta:
    width: int
    height: int
    duration: Optional[int]


def _boxes(
    data: bytes, start: int = 0, end: Optional[int] = None
) -> Iterator[tuple[bytes, int, int]]:
    """(type, payload start, payload end) for each box in data[start:end]."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack_from(">I4s", data, pos)
        header = 8
        if size == 1:
            if pos + 16 > end:
                return
            (size,) = struct.unpack_from(">Q", data, pos + 8)
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            return
        yield kind, pos + header, pos + size
        pos += size


def _read_moov(file: BinaryIO) -> Optional[bytes]:
    pos = 0
    while True:
        file.seek(pos)
        head = file.read(16)
        if len(head) < 8:
            return None
        size, kind = struct.unpack_from(">I4s", head)
        header = 8
        if size == 1 and len(head) == 16:
            (size,) = struct.unpack_from(">Q", head, 8)
            header = 16
        if size < header:
            return None
        if kind == b"moov":
            if size > _MAX_MOOV_BYTES:
                return None
            file.seek(pos + header)
            return file.read(size - header)
        pos += size


def _tkhd_size(data: bytes, start: int) -> tuple[int, int]:
    # version/flags, two times, track id, reserved, duration: 24 bytes, 36 in version 1;
    # then reserved, layer, group, volume, reserved: 16 bytes before the 3x3 matrix
    matrix = start + (36 if data[start] == 1 else 24) + 16
    a, b = struct.unpack_from(">ii", data, matrix)
    width, height = struct.unpack_from(">II", data, matrix + 36)
    width, height = width >> 16, height >> 16
    # a quarter turn in the display matrix: the picture is shown portrait
    return (height, width) if a == 0 and b != 0 else (width, height)


def _duration(data: bytes, start: int) -> Optional[int]:
    version = data[start]
    if version == 1:
        timescale, duration = struct.unpack_from(">IQ", data, start + 20)
    else:
        timescale, duration = struct.unpack_from(">II", data, start + 12)
    return round(duration / timescale) if timescale else None


def video_meta(path: Path) -> Optional[VideoMeta]:
    """Picture size and duration from an mp4's moov; None if it can't be read."""
    try:
        with path.open("rb") as file:
            moov = _read_moov(file)
        if moov is None:
            return None
        duration: Optional[int] = None
        size: Optional[tuple[int, int]] = None
        for kind, start, end in _boxes(moov):
            if kind == b"mvhd":
                duration = _duration(moov, start)
            elif kind == b"trak":
                for inner, inner_start, _ in _boxes(moov, start, end):
                    if inner == b"tkhd":
                        width, height = _tkhd_size(moov, inner_start)
                        # the audio track's tkhd is 0x0
                        if width and height and size is None:
                            size = (width, height)
    except (OSError, struct.error):
        return None
    if size is None:
        return None
    return VideoMeta(width=size[0], height=size[1], duration=duration)
