from cryptography.fernet import Fernet


def encrypt_value(value: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(value.encode()).decode()


def decrypt_value(value: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(value.encode()).decode()
