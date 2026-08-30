from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import get_app
from app.core.config import AppConfig


@pytest.fixture
def frontend_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (assets / "index-abc123.js").write_text("console.log('bundle')")
    (dist / "index.html").write_text("<html><body>spa shell</body></html>")
    (dist / "favicon.ico").write_text("icon")
    return dist


def test_health_returns_ok(config: AppConfig) -> None:
    app = get_app(config)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_without_frontend_dist_static_routes_are_not_mounted(
    config: AppConfig, tmp_path: Path
) -> None:
    app = get_app(config, frontend_dist=tmp_path / "does-not-exist")
    client = TestClient(app)

    response = client.get("/dashboard/settings")

    assert response.status_code == 404


def test_spa_fallback_serves_index_html_for_unknown_route(
    config: AppConfig, frontend_dist: Path
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    client = TestClient(app)

    response = client.get("/dashboard/settings")

    assert response.status_code == 200
    assert "spa shell" in response.text


def test_spa_fallback_serves_real_file_at_root(config: AppConfig, frontend_dist: Path) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    client = TestClient(app)

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.text == "icon"


def test_assets_are_served_from_assets_mount(config: AppConfig, frontend_dist: Path) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    client = TestClient(app)

    response = client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert "bundle" in response.text


def test_spa_fallback_rejects_path_traversal_outside_frontend_dist(
    config: AppConfig, frontend_dist: Path
) -> None:
    secret = frontend_dist.parent / "secret.txt"
    secret.write_text("top secret host file")

    app = get_app(config, frontend_dist=frontend_dist)
    client = TestClient(app)

    response = client.get("/%2e%2e/secret.txt")

    assert "top secret host file" not in response.text
    if response.status_code == 200:
        assert "spa shell" in response.text
    else:
        assert response.status_code in (400, 403, 404)
