from app.core.security.crypt import decrypt_value, encrypt_value

KEY = "lfhmZb2Nh7z4nlUbOz/0log2/hhnbtpssDkmW3AKLUM="


def test_encrypt_and_decrypt_roundtrip() -> None:
    ciphertext = encrypt_value("super-secret-bot-token", KEY)

    assert ciphertext != "super-secret-bot-token"
    assert decrypt_value(ciphertext, KEY) == "super-secret-bot-token"


def test_encrypt_is_not_deterministic() -> None:
    # random IV: equal ciphertexts would reveal equal secrets
    assert encrypt_value("same-value", KEY) != encrypt_value("same-value", KEY)
