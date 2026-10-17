from functools import lru_cache
from typing import Optional

from sqlalchemy.engine import Dialect
from sqlalchemy.types import String, TypeDecorator

from app.core.config import AppConfig
from app.core.security.crypt import decrypt_value, encrypt_value


@lru_cache(maxsize=1)
def _crypt_key() -> str:
    return AppConfig.get().crypt_key.get_secret_value()


class EncryptedString(TypeDecorator[str]):
    # mapped attributes stay plaintext; only the stored value is Fernet ciphertext

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect: Dialect) -> Optional[str]:
        if value is None:
            return None
        return encrypt_value(value, _crypt_key())

    def process_result_value(self, value: Optional[str], dialect: Dialect) -> Optional[str]:
        if value is None:
            return None
        return decrypt_value(value, _crypt_key())
