from app.core.security.session_token import generate_refresh_token, hash_refresh_token


def test_generate_refresh_token_is_url_safe_and_high_entropy() -> None:
    token_a = generate_refresh_token()
    token_b = generate_refresh_token()

    assert token_a != token_b
    assert len(token_a) >= 32


def test_hash_refresh_token_is_deterministic_and_hex() -> None:
    token = generate_refresh_token()

    first = hash_refresh_token(token)
    second = hash_refresh_token(token)

    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


def test_hash_refresh_token_differs_for_different_tokens() -> None:
    assert hash_refresh_token("token-a") != hash_refresh_token("token-b")
