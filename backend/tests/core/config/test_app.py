from pathlib import Path

from app.core.config import AppConfig


def test_media_dir_defaults_to_media_dir_constant(config: AppConfig) -> None:
    assert config.media_dir.name == "media"


def test_media_dir_is_overridable(config: AppConfig, tmp_path: Path) -> None:
    overridden = config.model_copy(update={"media_dir": tmp_path})
    assert overridden.media_dir == tmp_path
