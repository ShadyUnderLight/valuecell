from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient

import valuecell.server.api.app as app_module


def _empty_router() -> APIRouter:
    return APIRouter()


def test_app_product_path_smoke(monkeypatch, tmp_path: Path) -> None:
    """Smoke test app factory and product-path health endpoints."""
    db_path = tmp_path / "smoke.db"
    monkeypatch.setenv("VALUECELL_DATABASE_URL", f"sqlite:///{db_path}")

    # Keep smoke stable by skipping heavyweight router initialization side effects.
    monkeypatch.setattr(app_module, "create_agent_stream_router", _empty_router)
    monkeypatch.setattr(app_module, "create_strategy_api_router", _empty_router)

    app_module.get_settings.cache_clear()
    app = app_module.create_app()
    client = TestClient(app)

    root_response = client.get("/")
    assert root_response.status_code == 200
    root_payload = root_response.json()
    assert root_payload["code"] == 0
    assert root_payload["data"]["name"]
    assert root_payload["data"]["version"]
    assert root_payload["data"]["environment"]

    healthz_response = client.get("/api/v1/healthz")
    assert healthz_response.status_code == 200
    healthz_payload = healthz_response.json()
    assert healthz_payload["code"] == 0
    assert healthz_payload["msg"] == "Welcome to ValueCell!"

    system_health_response = client.get("/api/v1/system/health")
    assert system_health_response.status_code == 200
    system_health_payload = system_health_response.json()
    assert system_health_payload["code"] == 0
    assert system_health_payload["data"]["status"] == "healthy"

    config_health_response = client.get("/api/v1/system/config-health")
    assert config_health_response.status_code == 200
    config_health_payload = config_health_response.json()
    assert config_health_payload["code"] == 0
    assert config_health_payload["data"]["status"] in {"healthy", "warning", "error"}
    assert isinstance(config_health_payload["data"]["enabled_providers"], list)
    assert isinstance(config_health_payload["data"]["issues"], list)
