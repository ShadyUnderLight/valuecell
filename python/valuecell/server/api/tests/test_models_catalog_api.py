from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from valuecell.adapters.models.provider_inventory import ProviderInventoryModel
from valuecell.config.loader import ConfigLoader
from valuecell.config.manager import ConfigManager
from valuecell.config.model_resolver import ModelResolver
from valuecell.server.api.routers import models as models_router


def _write_main_config(base_dir: Path) -> None:
    (base_dir / "config.yaml").write_text(
        """
app:
  name: test
models:
  primary_provider: openai
""",
        encoding="utf-8",
    )


def _write_catalog_file(base_dir: Path, filename: str, content: str) -> None:
    catalog_dir = base_dir / "models" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / filename).write_text(content, encoding="utf-8")


def _write_provider_file(base_dir: Path, provider: str, content: str) -> None:
    providers_dir = base_dir / "providers"
    providers_dir.mkdir(parents=True, exist_ok=True)
    (providers_dir / f"{provider}.yaml").write_text(content, encoding="utf-8")


def _prepare_config(tmp_path: Path) -> None:
    _write_main_config(tmp_path)
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
  - id: gpt-next
    name: GPT Next
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
    loader = ConfigLoader(config_dir=tmp_path)
    manager = ConfigManager(loader=loader)
    monkeypatch.setattr(models_router, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(
        models_router,
        "get_model_resolver",
        lambda config_dir=None: ModelResolver.from_config(config_dir=tmp_path),
    )
    monkeypatch.setattr(models_router, "get_config_loader", lambda: loader)
    monkeypatch.setattr(models_router, "get_config_manager", lambda: manager)

    app = FastAPI()
    app.include_router(models_router.create_models_router(), prefix="/api/v1")
    return TestClient(app)


class _FakeProviderInventorySource:
    def __init__(self, items_by_provider: dict[str, list[ProviderInventoryModel]]) -> None:
        self._items_by_provider = items_by_provider

    async def list_models(self, provider: str) -> list[ProviderInventoryModel]:
        return list(self._items_by_provider.get(provider, []))


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


def test_validate_model_structured_legacy_id(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/models/validate",
        json={"provider": "openai", "model_id": "gpt-5"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["ok"] is False
    assert data["status"] == "auth_failed"
    assert data["model_id"] == "gpt-5"
    assert data["canonical_ref"] == "openai/gpt-5.4"
    assert data["resolved_provider"] == "openai"
    assert data["resolved_model_id"] == "gpt-5-2025-08-07"
    assert data["match_type"] == "legacy_id"

    stages = data["stages"]
    assert stages["catalog_known"] is True
    assert stages["provider_enabled"] is True
    assert stages["provider_configured"] is False
    assert stages["resolved"] is True
    assert stages["native_model_id_present"] is True
    assert stages["reachable"] is False
    assert stages["deprecated"] is False
    assert stages["preview"] is False


def test_validate_prefers_explicit_model_ref(tmp_path: Path, monkeypatch) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/models/validate",
        json={
            "provider": "openai",
            "model_ref": "openai/gpt-5.4",
            "model_id": "gpt-5",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["model_id"] == "gpt-5-2025-08-07"
    assert data["canonical_ref"] == "openai/gpt-5.4"
    assert data["resolved_model_id"] == "gpt-5-2025-08-07"
    assert data["match_type"] == "canonical_ref"
    assert data["stages"]["resolved"] is True


def test_validate_invalid_explicit_model_ref_does_not_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    _prepare_config(tmp_path)
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/models/validate",
        json={
            "provider": "openai",
            "model_ref": "openai/does-not-exist",
            "model_id": "gpt-5",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["ok"] is False
    assert data["status"] == "unresolved_model_ref"
    assert data["error"] == "Explicit model_ref 'openai/does-not-exist' could not be resolved"
    assert data["model_id"] == "openai/does-not-exist"
    assert data["canonical_ref"] is None
    assert data["resolved_provider"] is None
    assert data["resolved_model_id"] is None
    assert data["match_type"] is None

    stages = data["stages"]
    assert stages["catalog_known"] is False
    assert stages["resolved"] is False
    assert stages["native_model_id_present"] is False
    assert stages["reachable"] is False


def test_scan_provider_persists_state_and_does_not_auto_import(
    tmp_path: Path, monkeypatch
) -> None:
    _prepare_config(tmp_path)
    monkeypatch.setattr(
        models_router,
        "get_provider_inventory_source",
        lambda: _FakeProviderInventorySource(
            {
                "openai": [
                    ProviderInventoryModel(
                        model_id="provider-scan-only", model_name="Provider Scan Only"
                    )
                ]
            }
        ),
    )
    client = _build_client(tmp_path, monkeypatch)

    response = client.post("/api/v1/models/providers/openai/scan")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider"] == "openai"
    assert sorted(data["report"]["new_model_ids"]) == ["provider-scan-only"]
    assert data["report"]["missing_model_ids"] == ["gpt-5-2025-08-07"]
    assert data["report"]["renamed_model_ids"] == []
    assert data["report"]["deprecated_model_ids"] == []
    assert [item["model_id"] for item in data["candidates"]] == ["provider-scan-only"]

    scan_file = tmp_path / "models" / "scans" / "openai.yaml"
    assert scan_file.exists() is True

    catalog_response = client.get(
        "/api/v1/models/catalog", params={"provider": "openai", "query": "gpt-next"}
    )
    assert catalog_response.status_code == 200
    assert catalog_response.json()["data"] == []


def test_import_catalog_from_scan_selected_model_ids_only(
    tmp_path: Path, monkeypatch
) -> None:
    _prepare_config(tmp_path)
    monkeypatch.setattr(
        models_router,
        "get_provider_inventory_source",
        lambda: _FakeProviderInventorySource(
            {
                "openai": [
                    ProviderInventoryModel(
                        model_id="provider-scan-only", model_name="Provider Scan Only"
                    )
                ]
            }
        ),
    )
    client = _build_client(tmp_path, monkeypatch)

    scan_response = client.post("/api/v1/models/providers/openai/scan")
    assert scan_response.status_code == 200

    import_response = client.post(
        "/api/v1/models/catalog/import",
        json={
            "provider": "openai",
            "model_ids": ["provider-scan-only", "gpt-not-in-scan"],
        },
    )
    assert import_response.status_code == 200
    data = import_response.json()["data"]

    assert data["provider"] == "openai"
    assert len(data["imported"]) == 1
    assert data["imported"][0]["native_model_id"] == "provider-scan-only"
    assert data["imported"][0]["source"] == "imported"
    assert data["skipped_existing_model_ids"] == []
    assert data["missing_from_scan_model_ids"] == ["gpt-not-in-scan"]

    imported_file = tmp_path / "models" / "catalog" / "openai.imported.yaml"
    assert imported_file.exists() is True
    imported_text = imported_file.read_text(encoding="utf-8")
    assert "native_model_id: provider-scan-only" in imported_text
    assert "visibility: hidden" in imported_text
    assert "source: imported" in imported_text

    catalog_response = client.get(
        "/api/v1/models/catalog",
        params={"provider": "openai", "query": "provider-scan-only"},
    )
    assert catalog_response.status_code == 200
    assert len(catalog_response.json()["data"]) == 1
