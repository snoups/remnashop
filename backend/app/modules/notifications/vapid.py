from base64 import urlsafe_b64encode

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def _b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_vapid_keypair() -> tuple[str, str]:
    # public: the browser's applicationServerKey; private: raw 32 bytes,
    # which py_vapid's from_string accepts as is
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    private = key.private_numbers().private_value.to_bytes(32, "big")
    return _b64url(public), _b64url(private)
