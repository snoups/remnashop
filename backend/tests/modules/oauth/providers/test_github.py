import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from app.modules.oauth.providers.github import GitHubOAuthClient


async def test_authorization_url_carries_s256_code_challenge() -> None:
    verifier = "v" * 64
    client = GitHubOAuthClient("client-id", "client-secret")

    url = await client.authorization_url("https://shop.example.com/cb", "state-1", verifier)

    query = parse_qs(urlparse(url).query)
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [expected.decode()]
