import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Final, Optional

# Proof that a backup came from THIS deployment, checked by the CLI restore
# before pg_restore. Proves origin only, nothing is encrypted.
_MARKER: Final[bytes] = b"\n-- remnashop-backup-provenance v1 "
_TRAILER_SCAN_BYTES: Final[int] = 4096
_CHUNK_SIZE: Final[int] = 1024 * 1024


class ProvenanceStatus(Enum):
    NATIVE = auto()
    UNSTAMPED = auto()
    FOREIGN = auto()
    MALFORMED = auto()


@dataclass(frozen=True)
class ProvenanceResult:
    status: ProvenanceStatus


def _derive_key(crypt_key: str) -> bytes:
    # derived per use from APP_CRYPT_KEY, never the raw key (like the
    # password pepper in core/security/password.py)
    return hashlib.sha256(f"remnashop:backup-provenance:{crypt_key}".encode()).digest()


def _digest_body(path: Path, crypt_key: str, limit: Optional[int] = None) -> tuple[str, str]:
    sha = hashlib.sha256()
    mac = hmac.new(_derive_key(crypt_key), digestmod=hashlib.sha256)
    remaining = limit
    with path.open("rb") as f:
        while remaining is None or remaining > 0:
            size = _CHUNK_SIZE if remaining is None else min(_CHUNK_SIZE, remaining)
            chunk = f.read(size)
            if not chunk:
                break
            sha.update(chunk)
            mac.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return sha.hexdigest(), mac.hexdigest()


def sign_backup_file(path: Path, crypt_key: str) -> None:
    content_hash, signature = _digest_body(path, crypt_key)
    trailer = _MARKER + f"{content_hash} {signature}\n".encode()
    with path.open("ab") as f:
        f.write(trailer)


@dataclass(frozen=True)
class _Trailer:
    content_hash: str
    signature: str
    start_in_tail: int


def _parse_trailer(tail: bytes) -> _Trailer:
    idx = tail.rfind(_MARKER)
    if idx == -1:
        raise ValueError("no trailer marker found")
    line = tail[idx + len(_MARKER) :]
    if not line.endswith(b"\n"):
        raise ValueError("trailer does not end at end of file")
    content_hash, signature = line[:-1].decode().split(" ", 1)
    if len(content_hash) != 64 or len(signature) != 64:
        raise ValueError("malformed trailer fields")
    return _Trailer(content_hash=content_hash, signature=signature, start_in_tail=idx)


def verify_backup_file(path: Path, crypt_key: str) -> ProvenanceResult:
    with path.open("rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - _TRAILER_SCAN_BYTES))
        tail = f.read()

    try:
        trailer = _parse_trailer(tail)
    except ValueError:
        return ProvenanceResult(status=ProvenanceStatus.UNSTAMPED)

    trailer_start = size - len(tail) + trailer.start_in_tail
    content_hash, expected_signature = _digest_body(path, crypt_key, limit=trailer_start)

    if content_hash != trailer.content_hash:
        return ProvenanceResult(status=ProvenanceStatus.MALFORMED)

    if not hmac.compare_digest(expected_signature, trailer.signature):
        return ProvenanceResult(status=ProvenanceStatus.FOREIGN)

    return ProvenanceResult(status=ProvenanceStatus.NATIVE)
