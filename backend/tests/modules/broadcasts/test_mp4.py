from pathlib import Path

from app.modules.broadcasts.mp4 import VideoMeta, video_meta
from tests.modules.broadcasts.factories import QUARTER_TURN, mp4, tkhd


def test_reads_the_video_track_size_after_the_media_data(tmp_path: Path) -> None:
    file = tmp_path / "v.mp4"
    file.write_bytes(mp4(tkhd(0, 0), tkhd(3840, 2160)))

    assert video_meta(file) == VideoMeta(width=3840, height=2160, duration=24)


def test_a_quarter_turn_swaps_the_shown_size(tmp_path: Path) -> None:
    file = tmp_path / "v.mp4"
    file.write_bytes(mp4(tkhd(1920, 1080, QUARTER_TURN)))

    assert video_meta(file) == VideoMeta(width=1080, height=1920, duration=24)


def test_not_an_mp4(tmp_path: Path) -> None:
    file = tmp_path / "v.mp4"
    file.write_bytes(b"\x00\x00\x00\x02junk")

    assert video_meta(file) is None
