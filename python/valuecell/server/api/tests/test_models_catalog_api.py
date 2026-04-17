from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from valuecell.config.model_resolver import ModelResolver
from valuecell.server.api.routers import models as models_router


def _write_catalog_file(base_dir: Path, filename: str, content: str) -> None:
    catalog_dir = base_dir / "models" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / filename).write_text(content, encoding="utf-8")


def _write_provider_file(base_dir: Path, provider: str, content: str) -> None:
    providers_dir = base_dir / "providers"
    providers_dir.mkdir(parents=True, exist_ok=True)
    (providers_dir / f"{provider}.yaml").write_text(content, encoding="utf-8")


def _prepare_config(tmp_path: Path) -> None:
    _write_catalog_file(
        tmp_path,
        "openai.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: openai
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
    aliases:
      - gpt54
    status: stable
    visibility: default
    metadata:
      legacy_ids:
        - gpt-5
""",
    )
    _write_catalog_file(
        tmp_path,
        "google.yaml",
        """
entries:
  - ref: google/gemini-2.5-flash
    provider: google
    native_model_id: gemini-2.5-flash
    display_name: Gemini 2.5 Flash
    aliases:
      - gemini25-flash
    status: stable
    visibility: hidden
""",
    )

    _write_provider_file(
        tmp_path,
        "openai",
        """
default_model: gpt-5
models:
  - id: gpt-5
    name: GPT-5 Legacy
""",
    )
    _write_provider_file(
        tmp_path,
        "google",
        """
default_model: gemini-2.5-flash
models:
  - id: gemini-2.5-flash
    name: Gemini 2.5 Flash
""",
    )


def _build_client(tmp_path: Path, monkeypatch) -> TestClient:
    resolver = ModelResolver.from_config(config_dir=tmp_path)
    monkeypatch.setattr(models_router, "get_model_resolver", lambda config_dir=None: resolver)

    app = FastAPI()
    app.include_router(models_router.create_models_router(), prefix="/api/v1")
    return TestClient(app)


def test_get_models_catalog_with_filters(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/api/v1/models/catalog",
        params={"provider": "openai", "status": "stable", "query": "gpt"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert len(payload["data"]) == 1
    assert payload["data"][0]["canonical_ref"] == "openai/gpt-5.4"


def test_resolve_alias_via_api(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post("/api/v1/models/resolve", json={"model": "gpt54"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["canonical_ref"] == "openai/gpt-5.4"
    assert data["match_type"] == "alias"


def test_resolve_native_id_via_api(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/models/resolve", json={"model": "gpt-5-2025-08-07"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["canonical_ref"] == "openai/gpt-5.4"
    assert data["match_type"] == "native_id"


def test_resolve_legacy_id_via_api(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post("/api/v1/models/resolve", json={"model": "gpt-5"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["canonical_ref"] == "openai/gpt-5.4"
    assert data["match_type"] == "legacy_id"


def test_resolve_model_not_found(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post("/api/v1/models/resolve", json={"model": "unknown-model"})

    assert response.status_code == 404
