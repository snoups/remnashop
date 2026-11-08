from pathlib import Path

from app.modules.backups.provenance import ProvenanceStatus, sign_backup_file, verify_backup_file


def _write_dump(tmp_path: Path, content: bytes = b"fake pg_dump -Fc bytes") -> Path:
    path = tmp_path / "db.dump"
    path.write_bytes(content)
    return path


def test_signed_file_verifies_as_native(tmp_path: Path) -> None:
    path = _write_dump(tmp_path)
    sign_backup_file(path, "key-a")
    result = verify_backup_file(path, "key-a")
    assert result.status is ProvenanceStatus.NATIVE


def test_unsigned_file_is_unstamped(tmp_path: Path) -> None:
    path = _write_dump(tmp_path)
    result = verify_backup_file(path, "key-a")
    assert result.status is ProvenanceStatus.UNSTAMPED


def test_signed_with_different_key_is_foreign(tmp_path: Path) -> None:
    path = _write_dump(tmp_path)
    sign_backup_file(path, "key-a")
    # another deployment's key: the embedded signature matches only the same key
    result = verify_backup_file(path, "key-b")
    assert result.status is ProvenanceStatus.FOREIGN


def test_tampered_content_after_signing_is_malformed(tmp_path: Path) -> None:
    from app.modules.backups.provenance import _MARKER  # noqa: PLC0415

    path = _write_dump(tmp_path)
    sign_backup_file(path, "key-a")
    body = bytearray(path.read_bytes())
    marker_idx = body.rfind(_MARKER)
    hash_start = marker_idx + len(_MARKER)
    # the trailer still parses, only the hash no longer matches; appended bytes
    # would read as UNSTAMPED instead of MALFORMED
    body[hash_start] = ord("0") if body[hash_start] != ord("0") else ord("1")
    path.write_bytes(bytes(body))
    result = verify_backup_file(path, "key-a")
    assert result.status is ProvenanceStatus.MALFORMED
