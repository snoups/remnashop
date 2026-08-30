from app.core.security.password import (
    PASSWORD_MIN_LENGTH,
    generate_password,
    hash_password,
    verify_password,
)


def test_generate_password_default_length() -> None:
    assert len(generate_password()) == PASSWORD_MIN_LENGTH


def test_generate_password_custom_length() -> None:
    assert len(generate_password(length=32)) == 32


def test_generate_password_is_random() -> None:
    assert generate_password() != generate_password()


def test_generate_password_is_alphanumeric() -> None:
    assert generate_password().isalnum()


async def test_hash_and_verify_roundtrip() -> None:
    password = "Sup3rSecretPassw0rd1234567890"
    pepper = "test-pepper"

    hashed = await hash_password(password, pepper)

    assert await verify_password(password, hashed, pepper)


async def test_verify_rejects_wrong_password() -> None:
    hashed = await hash_password("correct-password-here-1234567890", "pepper")

    assert not await verify_password("wrong-password-here-1234567890", hashed, "pepper")


async def test_verify_rejects_wrong_pepper() -> None:
    hashed = await hash_password("some-password-here-1234567890", "pepper-a")

    assert not await verify_password("some-password-here-1234567890", hashed, "pepper-b")


async def test_hash_is_salted() -> None:
    password = "same-password-used-twice-1234567890"

    assert await hash_password(password, "pepper") != await hash_password(password, "pepper")
