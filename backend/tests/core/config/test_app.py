import base64
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import AppConfig


def test_media_dir_defaults_to_media_dir_constant(config: AppConfig) -> None:
    assert config.media_dir.name == "media"


def test_media_dir_is_overridable(config: AppConfig, tmp_path: Path) -> None:
    overridden = config.model_copy(update={"media_dir": tmp_path})
    assert overridden.media_dir == tmp_path


@pytest.mark.parametrize(
    "key",
    [
        Fernet.generate_key().decode(),  # url-safe alphabet, what Fernet emits
        base64.b64encode(b"\xfb" * 32).decode(),  # standard alphabet, openssl rand -base64 32
    ],
)
def test_crypt_key_accepts_every_shape_fernet_itself_accepts(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    monkeypatch.setenv("APP_CRYPT_KEY", key)
    assert AppConfig.get().crypt_key.get_secret_value() == key


@pytest.mark.parametrize("key", ["change_me", "too-short", "A" * 44])
def test_crypt_key_rejects_what_fernet_cannot_use(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    monkeypatch.setenv("APP_CRYPT_KEY", key)
    with pytest.raises(ValidationError):
        AppConfig.get()
