from pathlib import Path
from typing import Final

import pytest

from app.modules.backups.provenance import ProvenanceStatus, sign_backup_file, verify_backup_file

# verify_backup_file() reads its crypt key from AppConfig, which validates
# APP_CRYPT_KEY as a 44-char base64 string -- "key-a" alone can't stand in
# for it, so tests that exercise the public (config-backed) verify path
# monkeypatch the env var to this value and sign with the same value.
_TEST_CRYPT_KEY: Final[str] = "lfhmZb2Nh7z4nlUbOz/0log2/hhnbtpssDkmW3AKLUM="


def _write_dump(tmp_path: Path, content: bytes = b"fake pg_dump -Fc bytes") -> Path:
    path = tmp_path / "db.dump"
    path.write_bytes(content)
    return path


def test_signed_file_verifies_as_native(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CRYPT_KEY", _TEST_CRYPT_KEY)
    path = _write_dump(tmp_path)
    sign_backup_file(path, _TEST_CRYPT_KEY)
    result = verify_backup_file(path)
    assert result.status is ProvenanceStatus.NATIVE


def test_unsigned_file_is_unstamped(tmp_path: Path) -> None:
    path = _write_dump(tmp_path)
    result = verify_backup_file(path)
    assert result.status is ProvenanceStatus.UNSTAMPED


def test_signed_with_different_key_is_foreign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_CRYPT_KEY", _TEST_CRYPT_KEY)
    path = _write_dump(tmp_path)
    sign_backup_file(path, _TEST_CRYPT_KEY)
    result = verify_backup_file(path)
    assert result.status is ProvenanceStatus.NATIVE

    # simulate verifying under a different deployment's key by re-deriving
    # with a different crypt key -- verify_backup_file reads the trailer's
    # own embedded signature and needs the SAME key passed in to match it.
    from app.modules.backups.provenance import _verify_with_key  # noqa: PLC0415 -- reach-in

    mismatched = _verify_with_key(path, "key-b")
    assert mismatched.status is ProvenanceStatus.FOREIGN


def test_tampered_content_after_signing_is_malformed(tmp_path: Path) -> None:
    from app.modules.backups.provenance import _MARKER  # noqa: PLC0415 -- test-only reach-in

    path = _write_dump(tmp_path)
    sign_backup_file(path, "key-a")
    body = bytearray(path.read_bytes())
    marker_idx = body.rfind(_MARKER)
    hash_start = marker_idx + len(_MARKER)
    # flip the first hex char of the embedded content-hash: the trailer
    # still parses cleanly (marker found, line ends in "\n"), but the hash
    # no longer matches the real body. Appending bytes after the trailer
    # instead breaks the "ends with \n" check and is reported as
    # UNSTAMPED (no trailer found), not MALFORMED.
    body[hash_start] = ord("0") if body[hash_start] != ord("0") else ord("1")
    path.write_bytes(bytes(body))
    result = verify_backup_file(path)
    assert result.status is ProvenanceStatus.MALFORMED
