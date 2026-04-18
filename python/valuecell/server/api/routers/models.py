"""Models API router: provide LLM model configuration defaults."""

import os
from pathlib import Path
from typing import List

import yaml
from fastapi import APIRouter, HTTPException, Query

from valuecell.config.constants import CONFIG_DIR
from valuecell.config.loader import get_config_loader
from valuecell.config.manager import get_config_manager
from valuecell.config.model_catalog import ModelCatalogEntry
from valuecell.config.model_resolver import ModelResolution, ModelResolver
from valuecell.utils.env import get_system_env_path

from ..schemas import SuccessResponse
from ..schemas.model import (
    AddModelRequest,
    CheckModelRequest,
    CheckModelResponse,
    CatalogModelItem,
    ModelValidationStages,
    ModelItem,
    ModelProviderSummary,
    ProviderDetailData,
    ProviderModelEntry,
    ProviderUpdateRequest,
    ResolveModelRequest,
    ResolveModelResponse,
    SetDefaultModelRequest,
    SetDefaultProviderRequest,
)

# Optional fallback constants from StrategyAgent
try:
    from valuecell.agents.common.trading.constants import (
        DEFAULT_AGENT_MODEL,
        DEFAULT_MODEL_PROVIDER,
    )
except Exception:  # pragma: no cover - constants may not exist in minimal env
    DEFAULT_MODEL_PROVIDER = "openrouter"
    DEFAULT_AGENT_MODEL = "gpt-4o"


def get_model_resolver(config_dir: Path | None = None) -> ModelResolver:
    """Create a model resolver backed by the configured catalog and provider YAMLs."""
    resolved_config_dir = CONFIG_DIR if config_dir is None else config_dir
    return ModelResolver.from_config(config_dir=resolved_config_dir)


def create_models_router() -> APIRouter:
    """Create models-related router with endpoints for model configs and provider management."""

    router = APIRouter(prefix="/models", tags=["Models"])

    # ---- Utility helpers (local to router) ----
    def _env_paths() -> List[Path]:
        """Return only system .env path for writes (single source of truth)."""
        system_env = get_system_env_path()
        return [system_env]

    def _set_env(key: str, value: str) -> bool:
        os.environ[key] = value
        updated_any = False
        for env_file in _env_paths():
            # Ensure parent directory exists for system env file
            try:
                env_file.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                # Best effort; continue even if directory creation fails
                pass
            lines: List[str] = []
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            updated = False
            found = False
            new_lines: List[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                    updated = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"{key}={value}\n")
                updated = True
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            updated_any = updated_any or updated
        return updated_any

    def _provider_yaml(provider: str) -> Path:
        return CONFIG_DIR / "providers" / f"{provider}.yaml"

    def _load_yaml(path: Path) -> dict:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _write_yaml(path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

    def _refresh_configs() -> None:
        loader = get_config_loader()
        loader.clear_cache()
        manager = get_config_manager()
        manager._config = manager.loader.load_config()

    def _preferred_provider_order(names: List[str]) -> List[str]:
        """Return providers ordered with preferred defaults first.

        Ensures 'openrouter' is first and 'siliconflow' is second when present,
        followed by the remaining providers in their original order.
        """
        preferred = ["openrouter", "siliconflow"]
        seen = set()
        ordered: List[str] = []

        # Add preferred providers in order if they exist
        for p in preferred:
            if p in names and p not in seen:
                ordered.append(p)
                seen.add(p)

        # Append the rest while preserving original order
        for name in names:
            if name not in seen:
                ordered.append(name)
                seen.add(name)

        return ordered

    def _api_key_url_for(provider: str) -> str | None:
        """Return the URL for obtaining an API key for the given provider."""
        mapping = {
            "google": "https://aistudio.google.com/app/api-keys",
            "openrouter": "https://openrouter.ai/settings/keys",
            "openai": "https://platform.openai.com/api-keys",
            "azure": "https://azure.microsoft.com/en-us/products/ai-foundry/models/openai/",
            "siliconflow": "https://cloud.siliconflow.cn/account/ak",
            "deepseek": "https://platform.deepseek.com/api_keys",
            "dashscope": "https://bailian.console.aliyun.com/#/home",
            "ollama": None,
        }
        return mapping.get(provider)

    def _to_catalog_item(entry: ModelCatalogEntry) -> CatalogModelItem:
        return CatalogModelItem(
            canonical_ref=entry.ref,
            provider=entry.provider,
            native_model_id=entry.native_model_id,
            display_name=entry.display_name,
            status=entry.status,
            visibility=entry.visibility,
        )

    def _contains_query(entry, query: str) -> bool:
        lowered_query = query.lower()
        if lowered_query in entry.ref.lower():
            return True
        if lowered_query in entry.provider.lower():
            return True
        if lowered_query in entry.native_model_id.lower():
            return True
        if lowered_query in entry.display_name.lower():
            return True

        for alias in entry.aliases:
            if lowered_query in alias.lower():
                return True
        return False

    @router.get(
        "/catalog",
        response_model=SuccessResponse[List[CatalogModelItem]],
        summary="List model catalog entries",
        description=(
            "List canonical model catalog entries. "
            "Supports optional filtering by provider, status, visibility, and query."
        ),
    )
    async def list_model_catalog(
        provider: str | None = Query(
            default=None, description="Filter by provider (case-insensitive)"
        ),
        status: str | None = Query(
            default=None, description="Filter by catalog status (case-insensitive)"
        ),
        visibility: str | None = Query(
            default=None, description="Filter by catalog visibility (case-insensitive)"
        ),
        query: str | None = Query(
            default=None,
            description=(
                "Filter by free-text query across ref, provider, native model id, "
                "display name, and aliases"
            ),
        ),
    ) -> SuccessResponse[List[CatalogModelItem]]:
        try:
            resolver = get_model_resolver()
            entries = list(resolver.catalog.entries)

            normalized_provider = provider.strip().lower() if provider else None
            normalized_status = status.strip().lower() if status else None
            normalized_visibility = visibility.strip().lower() if visibility else None
            normalized_query = query.strip().lower() if query else None

            if normalized_provider:
                entries = [
                    entry
                    for entry in entries
                    if entry.provider.lower() == normalized_provider
                ]
            if normalized_status:
                entries = [
                    entry
                    for entry in entries
                    if (entry.status or "").strip().lower() == normalized_status
                ]
            if normalized_visibility:
                entries = [
                    entry
                    for entry in entries
                    if (entry.visibility or "").strip().lower() == normalized_visibility
                ]
            if normalized_query:
                entries = [
                    entry
                    for entry in entries
                    if _contains_query(entry=entry, query=normalized_query)
                ]

            data = [_to_catalog_item(entry) for entry in entries]
            return SuccessResponse.create(data=data, msg=f"Retrieved {len(data)} models")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to list model catalog: {e}"
            )

    @router.post(
        "/resolve",
        response_model=SuccessResponse[ResolveModelResponse],
        summary="Resolve model identifier",
        description=(
            "Resolve canonical refs, aliases, native model ids, or legacy ids "
            "into a canonical catalog model entry."
        ),
    )
    async def resolve_model(
        payload: ResolveModelRequest,
    ) -> SuccessResponse[ResolveModelResponse]:
        try:
            resolver = get_model_resolver()
            resolution = resolver.resolve(
                identifier=payload.model, provider=payload.provider
            )

            if resolution is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Model '{payload.model}' could not be resolved"
                        if payload.provider is None
                        else (
                            f"Model '{payload.model}' could not be resolved "
                            f"for provider '{payload.provider}'"
                        )
                    ),
                )

            data = ResolveModelResponse(
                canonical_ref=resolution.entry.ref,
                provider=resolution.entry.provider,
                native_model_id=resolution.entry.native_model_id,
                display_name=resolution.entry.display_name,
                match_type=resolution.match_type,
            )
            return SuccessResponse.create(data=data, msg="Model resolved")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to resolve model: {e}")

    @router.get(
        "/providers",
        response_model=SuccessResponse[List[ModelProviderSummary]],
        summary="List model providers",
        description="List available providers with status and basics.",
    )
    async def list_providers() -> SuccessResponse[List[ModelProviderSummary]]:
        try:
            manager = get_config_manager()
            loader = get_config_loader()
            # Prefer default ordering: openrouter first, siliconflow second
            names = _preferred_provider_order(loader.list_providers())
            items: List[ModelProviderSummary] = []
            for name in names:
                cfg = manager.get_provider_config(name)
                if not cfg:
                    continue
                items.append(
                    ModelProviderSummary(
                        provider=cfg.name,
                    )
                )
            return SuccessResponse.create(
                data=items, msg=f"Retrieved {len(items)} providers"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to list providers: {e}"
            )

    @router.get(
        "/providers/{provider}",
        response_model=SuccessResponse[ProviderDetailData],
        summary="Get provider details",
        description="Get configuration and models for a provider.",
    )
    async def get_provider_detail(provider: str) -> SuccessResponse[ProviderDetailData]:
        try:
            manager = get_config_manager()
            cfg = manager.get_provider_config(provider)
            if cfg is None:
                raise HTTPException(
                    status_code=404, detail=f"Provider '{provider}' not found"
                )
            models_entries: List[ProviderModelEntry] = []
            for m in cfg.models or []:
                if isinstance(m, dict):
                    mid = m.get("id")
                    name = m.get("name")
                    if mid:
                        models_entries.append(
                            ProviderModelEntry(model_id=mid, model_name=name)
                        )
            detail = ProviderDetailData(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                is_default=(cfg.name == manager.primary_provider),
                default_model_id=cfg.default_model,
                api_key_url=_api_key_url_for(cfg.name),
                models=models_entries,
            )
            return SuccessResponse.create(
                data=detail, msg=f"Provider '{provider}' details"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get provider: {e}")

    @router.put(
        "/providers/{provider}/config",
        response_model=SuccessResponse[ProviderDetailData],
        summary="Update provider config",
        description="Update provider API key and host, then refresh configs.",
    )
    async def update_provider_config(
        provider: str, payload: ProviderUpdateRequest
    ) -> SuccessResponse[ProviderDetailData]:
        try:
            loader = get_config_loader()
            provider_raw = loader.load_provider_config(provider)
            if not provider_raw:
                raise HTTPException(
                    status_code=404, detail=f"Provider '{provider}' not found"
                )

            connection = provider_raw.get("connection", {})
            api_key_env = connection.get("api_key_env")
            endpoint_env = connection.get("endpoint_env")

            # Update API key via env var
            # Accept empty string as a deliberate clear; skip only when field is omitted
            if api_key_env and (payload.api_key is not None):
                _set_env(api_key_env, payload.api_key)

            # Update base_url via env when endpoint_env exists (Azure),
            # otherwise prefer updating the env placeholder if present; fallback to YAML
            # Accept empty string as a deliberate clear; skip only when field is omitted
            if payload.base_url is not None:
                if endpoint_env:
                    _set_env(endpoint_env, payload.base_url)
                else:
                    # Try to detect ${ENV_VAR:default} syntax in provider YAML
                    path = _provider_yaml(provider)
                    data = _load_yaml(path)
                    connection_raw = data.get("connection", {})
                    raw_base = connection_raw.get("base_url")
                    env_var_name = None
                    if (
                        isinstance(raw_base, str)
                        and raw_base.startswith("${")
                        and "}" in raw_base
                    ):
                        try:
                            inner = raw_base[2 : raw_base.index("}")]
                            env_var_name = inner.split(":", 1)[0]
                        except Exception:
                            env_var_name = None

                    if env_var_name:
                        _set_env(env_var_name, payload.base_url)
                    else:
                        data.setdefault("connection", {})
                        data["connection"]["base_url"] = payload.base_url
                        _write_yaml(path, data)

            _refresh_configs()

            # Return updated detail
            manager = get_config_manager()
            cfg = manager.get_provider_config(provider)
            if not cfg:
                raise HTTPException(
                    status_code=500, detail="Provider not found after update"
                )
            models_items = [
                ProviderModelEntry(model_id=m.get("id", ""), model_name=m.get("name"))
                for m in (cfg.models or [])
                if isinstance(m, dict)
            ]

            detail = ProviderDetailData(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                is_default=(cfg.name == manager.primary_provider),
                default_model_id=cfg.default_model,
                models=models_items,
            )
            return SuccessResponse.create(
                data=detail, msg=f"Provider '{provider}' config updated"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update provider config: {e}"
            )

    @router.post(
        "/providers/{provider}/models",
        response_model=SuccessResponse[ModelItem],
        summary="Add provider model",
        description="Add a model id to provider YAML.",
    )
    async def add_provider_model(
        provider: str, payload: AddModelRequest
    ) -> SuccessResponse[ModelItem]:
        try:
            path = _provider_yaml(provider)
            data = _load_yaml(path)
            if not data:
                raise HTTPException(
                    status_code=404, detail=f"Provider '{provider}' not found"
                )
            models = data.get("models") or []
            for m in models:
                if isinstance(m, dict) and m.get("id") == payload.model_id:
                    if payload.model_name:
                        m["name"] = payload.model_name
                    # If provider has no default model, set this one as default
                    existing_default = str(data.get("default_model", "")).strip()
                    if not existing_default:
                        data["default_model"] = payload.model_id
                    _write_yaml(path, data)
                    _refresh_configs()
                    return SuccessResponse.create(
                        data=ModelItem(
                            model_id=payload.model_id, model_name=m.get("name")
                        ),
                        msg=(
                            "Model already exists; updated model_name if provided"
                            + ("; set as default model" if not existing_default else "")
                        ),
                    )
            models.append(
                {"id": payload.model_id, "name": payload.model_name or payload.model_id}
            )
            data["models"] = models
            # If provider has no default model, set the added one as default
            existing_default = str(data.get("default_model", "")).strip()
            if not existing_default:
                data["default_model"] = payload.model_id
            _write_yaml(path, data)
            _refresh_configs()
            return SuccessResponse.create(
                data=ModelItem(
                    model_id=payload.model_id,
                    model_name=payload.model_name or payload.model_id,
                ),
                msg="Model added"
                + ("; set as default model" if not existing_default else ""),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add model: {e}")

    @router.delete(
        "/providers/{provider}/models",
        response_model=SuccessResponse[dict],
        summary="Remove provider model",
        description="Remove a model id from provider YAML.",
    )
    async def remove_provider_model(
        provider: str,
        model_id: str = Query(..., description="Model identifier to remove"),
    ) -> SuccessResponse[dict]:
        try:
            path = _provider_yaml(provider)
            data = _load_yaml(path)
            if not data:
                raise HTTPException(
                    status_code=500, detail=f"Provider '{provider}' not found"
                )
            models = data.get("models") or []
            before = len(models)
            models = [
                m
                for m in models
                if not (isinstance(m, dict) and m.get("id") == model_id)
            ]
            after = len(models)
            data["models"] = models
            _write_yaml(path, data)
            _refresh_configs()
            removed = before != after
            return SuccessResponse.create(
                data={"removed": removed, "remaining": after},
                msg="Model removed" if removed else "Model not found",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove model: {e}")

    @router.put(
        "/providers/default",
        response_model=SuccessResponse[dict],
        summary="Set default provider",
        description="Set PRIMARY_PROVIDER via env and refresh configs.",
    )
    async def set_default_provider(
        payload: SetDefaultProviderRequest,
    ) -> SuccessResponse[dict]:
        try:
            _set_env("PRIMARY_PROVIDER", payload.provider)
            _refresh_configs()
            manager = get_config_manager()
            return SuccessResponse.create(
                data={"primary_provider": manager.primary_provider},
                msg=f"Primary provider set to '{payload.provider}'",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to set default provider: {e}"
            )

    @router.put(
        "/providers/{provider}/default-model",
        response_model=SuccessResponse[ProviderDetailData],
        summary="Set provider default model",
        description="Update provider default_model in YAML and refresh configs.",
    )
    async def set_provider_default_model(
        provider: str, payload: SetDefaultModelRequest
    ) -> SuccessResponse[ProviderDetailData]:
        try:
            path = _provider_yaml(provider)
            data = _load_yaml(path)
            if not data:
                raise HTTPException(
                    status_code=404, detail=f"Provider '{provider}' not found"
                )

            # Ensure the model exists in the list and optionally update name
            models = data.get("models") or []
            found = False
            for m in models:
                if isinstance(m, dict) and m.get("id") == payload.model_id:
                    if payload.model_name:
                        m["name"] = payload.model_name
                    found = True
                    break
            if not found:
                models.append(
                    {
                        "id": payload.model_id,
                        "name": payload.model_name or payload.model_id,
                    }
                )
            data["models"] = models

            # Set default model
            data["default_model"] = payload.model_id
            _write_yaml(path, data)
            _refresh_configs()

            # Build response from refreshed config
            manager = get_config_manager()
            cfg = manager.get_provider_config(provider)
            if not cfg:
                raise HTTPException(
                    status_code=500, detail="Provider not found after update"
                )
            models_items = [
                ProviderModelEntry(model_id=m.get("id", ""), model_name=m.get("name"))
                for m in (cfg.models or [])
                if isinstance(m, dict)
            ]
            detail = ProviderDetailData(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                is_default=(cfg.name == manager.primary_provider),
                default_model_id=cfg.default_model,
                models=models_items,
            )
            return SuccessResponse.create(
                data=detail,
                msg=(f"Default model for '{provider}' set to '{payload.model_id}'"),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to set default model: {e}"
            )

    @router.post(
        "/check",
        response_model=SuccessResponse[CheckModelResponse],
        summary="Check model availability",
        description=(
            "Perform a minimal live request to verify the model responds. "
            "Response includes structured validation stages for UI diagnostics."
        ),
    )
    async def check_model(
        payload: CheckModelRequest,
    ) -> SuccessResponse[CheckModelResponse]:
        def _clean_string(value: str | None) -> str | None:
            if not isinstance(value, str):
                return None
            normalized = value.strip()
            return normalized or None

        def _resolve_validation_model_id(
            *,
            resolver: ModelResolver,
            provider_name: str,
            provider_default_model_ref: str | None,
            provider_default_model_id: str | None,
            explicit_model_ref: str | None,
            explicit_model_id: str | None,
        ) -> tuple[str | None, ModelResolution | None, bool]:
            if explicit_model_ref:
                resolution = resolver.resolve(explicit_model_ref, provider=provider_name)
                if resolution is not None:
                    return resolution.entry.native_model_id, resolution, False
                return explicit_model_ref, None, True

            if explicit_model_id:
                resolution = resolver.resolve(explicit_model_id, provider=provider_name)
                return explicit_model_id, resolution, False

            if provider_default_model_ref:
                resolution = resolver.resolve(
                    provider_default_model_ref, provider=provider_name
                )
                if resolution is not None:
                    return resolution.entry.native_model_id, resolution, False

            if provider_default_model_id:
                resolution = resolver.resolve(
                    provider_default_model_id, provider=provider_name
                )
                return provider_default_model_id, resolution, False

            return None, None, False

        def _is_provider_configured(
            *,
            provider_name: str,
            is_enabled: bool,
            api_key_value: str,
            base_url_value: str,
        ) -> bool:
            if not is_enabled:
                return False
            if provider_name != "ollama" and not api_key_value:
                return False
            if provider_name in {"azure", "openai-compatible"} and not base_url_value:
                return False
            return True

        try:
            manager = get_config_manager()
            provider = payload.provider or manager.primary_provider
            cfg = manager.get_provider_config(provider)
            if cfg is None:
                raise HTTPException(
                    status_code=404, detail=f"Provider '{provider}' not found"
                )

            api_key = (payload.api_key or cfg.api_key or "").strip()
            base_url = (getattr(cfg, "base_url", None) or "").strip()
            resolver = get_model_resolver()

            explicit_model_ref = _clean_string(payload.model_ref)
            model_id, resolution, explicit_model_ref_unresolved = (
                _resolve_validation_model_id(
                    resolver=resolver,
                    provider_name=provider,
                    provider_default_model_ref=_clean_string(cfg.default_model_ref),
                    provider_default_model_id=_clean_string(cfg.default_model),
                    explicit_model_ref=explicit_model_ref,
                    explicit_model_id=_clean_string(payload.model_id),
                )
            )
            if explicit_model_ref_unresolved:
                result = CheckModelResponse(
                    ok=False,
                    provider=provider,
                    model_id=explicit_model_ref or "",
                    status="unresolved_model_ref",
                    error=f"Explicit model_ref '{explicit_model_ref}' could not be resolved",
                    canonical_ref=None,
                    resolved_provider=None,
                    resolved_model_id=None,
                    match_type=None,
                    stages=ModelValidationStages(
                        catalog_known=False,
                        provider_enabled=bool(cfg.enabled),
                        provider_configured=_is_provider_configured(
                            provider_name=provider,
                            is_enabled=bool(cfg.enabled),
                            api_key_value=api_key,
                            base_url_value=base_url,
                        ),
                        resolved=False,
                        native_model_id_present=False,
                        reachable=False,
                        deprecated=False,
                        preview=False,
                    ),
                )
                return SuccessResponse.create(data=result, msg="Model validation completed")

            if not model_id:
                raise HTTPException(
                    status_code=400,
                    detail="Model id not specified and provider has no default",
                )

            normalized_status = ""
            if resolution is not None and isinstance(resolution.entry.status, str):
                normalized_status = resolution.entry.status.strip().lower()

            # Perform a minimal live request (ping) without configuration validation
            result = CheckModelResponse(
                ok=False,
                provider=provider,
                model_id=model_id,
                status=None,
                error=None,
                canonical_ref=resolution.entry.ref if resolution else None,
                resolved_provider=resolution.entry.provider if resolution else None,
                resolved_model_id=(
                    resolution.entry.native_model_id if resolution else None
                ),
                match_type=resolution.match_type if resolution else None,
                stages=ModelValidationStages(
                    catalog_known=resolution is not None,
                    provider_enabled=bool(cfg.enabled),
                    provider_configured=_is_provider_configured(
                        provider_name=provider,
                        is_enabled=bool(cfg.enabled),
                        api_key_value=api_key,
                        base_url_value=base_url,
                    ),
                    resolved=resolution is not None,
                    native_model_id_present=bool(model_id),
                    reachable=False,
                    deprecated=normalized_status in {"deprecated", "retired", "sunset"},
                    preview=normalized_status in {"preview", "beta", "experimental"},
                ),
            )
            try:
                import asyncio

                import httpx
            except Exception as e:
                result.ok = False
                result.status = "runtime_missing"
                result.error = f"Runtime dependency missing: {e}"
                return SuccessResponse.create(data=result, msg="Live check failed")

            # Prefer a direct minimal request for OpenAI-compatible providers.
            # This avoids hidden fallbacks and validates API key/auth.
            # Use direct request timeout only (no agent fallback)
            direct_timeout_s = 5.0
            if provider == "google":
                direct_timeout_s = 30.0

            def _normalize_model_id_for_provider(provider_name: str, mid: str) -> str:
                """Normalize model id for specific providers to avoid 404s.

                - Google Gemini: sometimes configs use vendor-prefixed ids like
                  "google/gemini-1.5-flash"; the REST path expects just the model
                  name segment (e.g., "gemini-1.5-flash").
                - Other providers: return as-is.
                """
                if provider_name == "google" and "/" in mid:
                    return mid.split("/")[-1]
                return mid

            normalized_model_id = _normalize_model_id_for_provider(provider, model_id)

            async def _direct_openai_like_ping(endpoint: str) -> bool:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                json_body = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "temperature": 0,
                }
                async with httpx.AsyncClient(timeout=direct_timeout_s) as client:
                    resp = await client.post(endpoint, headers=headers, json=json_body)
                # Handle auth failures explicitly
                if resp.status_code in (401, 403):
                    try:
                        err_json = resp.json()
                        msg = err_json.get("error", {}).get("message") or str(err_json)
                    except Exception:
                        msg = resp.text
                    result.ok = False
                    result.status = "auth_failed"
                    result.error = msg or "Unauthorized"
                    return False
                if resp.status_code >= 400:
                    # Other request failures
                    try:
                        err_json = resp.json()
                        msg = err_json.get("error", {}).get("message") or str(err_json)
                    except Exception:
                        msg = resp.text
                    result.ok = False
                    result.status = "request_failed"
                    result.error = msg or f"HTTP {resp.status_code}"
                    return False
                # Success path: verify minimal structure
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if not data or "choices" not in data:
                    result.ok = False
                    result.status = "request_failed"
                    result.error = "Unexpected response structure"
                    return False
                result.status = "reachable"
                result.ok = True
                result.stages.reachable = True
                return True

            async def _direct_google_ping(endpoint: str) -> bool:
                # Gemini REST uses api key via query param `key`, but we also
                # set header to be safe.
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                }
                json_body = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": "ping"}],
                        }
                    ]
                }
                async with httpx.AsyncClient(timeout=direct_timeout_s) as client:
                    resp = await client.post(
                        endpoint,
                        headers=headers,
                        params={"key": api_key} if api_key else None,
                        json=json_body,
                    )

                if resp.status_code in (401, 403):
                    try:
                        err_json = resp.json()
                        msg = err_json.get("error", {}).get("message") or str(err_json)
                    except Exception:
                        msg = resp.text
                    result.ok = False
                    result.status = "auth_failed"
                    result.error = msg or "Unauthorized"
                    return False
                if resp.status_code >= 400:
                    try:
                        err_json = resp.json()
                        msg = err_json.get("error", {}).get("message") or str(err_json)
                    except Exception:
                        msg = resp.text
                    result.ok = False
                    result.status = "request_failed"
                    # Preserve HTTP code in error to enable v1/v1beta fallback on 404
                    if msg:
                        result.error = f"HTTP {resp.status_code}: {msg}"
                    else:
                        result.error = f"HTTP {resp.status_code}"
                    return False
                # Minimal success: presence of candidates
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if not data or "candidates" not in data:
                    result.ok = False
                    result.status = "request_failed"
                    result.error = "Unexpected response structure"
                    return False
                result.status = "reachable"
                result.ok = True
                result.stages.reachable = True
                return True

            def _normalize_base_url(url: str) -> str:
                return (url or "").strip().rstrip("/")

            def _resolve_endpoint() -> tuple[str | None, str]:
                """Return (endpoint, style) where style in {"openai_like", "google", "azure"}.

                Priority: if base_url provided, derive from host; else fall back to known provider mappings.
                """
                bu = _normalize_base_url(base_url)
                # Host-driven detection
                if bu:
                    lower = bu.lower()
                    if (
                        "generativelanguage.googleapis.com" in lower
                        or "googleapis.com" in lower
                    ):
                        # Construct Google endpoint for fast direct ping
                        # Handle cases where base_url already includes '/models' or full ':generateContent' path
                        if ":generatecontent" in lower:
                            # Treat as full endpoint
                            return bu, "google"
                        if "/models/" in lower:
                            # If base_url already includes '/models', avoid duplicating
                            if lower.endswith("/models"):
                                endpoint = f"{bu}/{normalized_model_id}:generateContent"
                            else:
                                # base_url might be '/models/{model}', append ':generateContent' if missing
                                endpoint = (
                                    f"{bu}:generateContent"
                                    if not lower.endswith(":generatecontent")
                                    else bu
                                )
                            return endpoint, "google"
                        # If base_url already includes version segment, do not repeat it
                        if lower.endswith("/v1beta") or "/v1beta/" in lower:
                            endpoint = (
                                f"{bu}/models/{normalized_model_id}:generateContent"
                            )
                        elif lower.endswith("/v1") or "/v1/" in lower:
                            endpoint = (
                                f"{bu}/models/{normalized_model_id}:generateContent"
                            )
                        else:
                            endpoint = f"{bu}/v1beta/models/{normalized_model_id}:generateContent"
                        return endpoint, "google"
                    if "openai.azure.com" in lower or "/openai/deployments" in lower:
                        # If user pasted a deployments URL, keep it; otherwise construct from base_url
                        # Azure requires api_version
                        api_version = (
                            getattr(cfg, "extra_config", {}).get("api_version")
                            if hasattr(cfg, "extra_config")
                            else None
                        )
                        if not api_version:
                            return None, "azure"
                        endpoint = f"{bu}/openai/deployments/{model_id}/chat/completions?api-version={api_version}"
                        return endpoint, "azure"
                    if "openrouter.ai" in lower:
                        return f"{bu}/api/v1/chat/completions" if not lower.endswith(
                            "/api/v1"
                        ) else f"{bu}/chat/completions", "openai_like"
                    if "openai.com" in lower:
                        return f"{bu}/v1/chat/completions" if not lower.endswith(
                            "/v1"
                        ) else f"{bu}/chat/completions", "openai_like"
                    if "deepseek.com" in lower:
                        return f"{bu}/v1/chat/completions" if not lower.endswith(
                            "/v1"
                        ) else f"{bu}/chat/completions", "openai_like"
                    if "siliconflow" in lower:
                        return f"{bu}/v1/chat/completions" if not lower.endswith(
                            "/v1"
                        ) else f"{bu}/chat/completions", "openai_like"
                    if "dashscope.aliyuncs.com" in lower or "dashscope.com" in lower:
                        # DashScope OpenAI-compatible endpoint lives under compatible-mode
                        if lower.endswith("/compatible-mode/v1"):
                            return f"{bu}/chat/completions", "openai_like"
                        return (
                            f"{bu}/compatible-mode/v1/chat/completions",
                            "openai_like",
                        )
                    # If base_url provided but host is unrecognized:
                    # - For openai-compatible, treat as generic OpenAI-like
                    # - For Google/Azure, ignore base_url and fall through to provider fallback
                    # - For other providers, fall through to provider fallback to use official endpoints
                    if provider == "openai-compatible":
                        return f"{bu}/v1/chat/completions", "openai_like"

                # Provider-driven fallback
                if provider == "google":
                    # Official Google endpoint for direct ping (v1beta by default)
                    return (
                        f"https://generativelanguage.googleapis.com/v1beta/models/{normalized_model_id}:generateContent",
                        "google",
                    )
                if provider == "azure":
                    api_version = (
                        getattr(cfg, "extra_config", {}).get("api_version")
                        if hasattr(cfg, "extra_config")
                        else None
                    )
                    if base_url and api_version:
                        endpoint = f"{base_url}/openai/deployments/{model_id}/chat/completions?api-version={api_version}"
                        return endpoint, "azure"
                    return None, "azure"
                if provider == "openai":
                    return "https://api.openai.com/v1/chat/completions", "openai_like"
                if provider == "openrouter":
                    return (
                        "https://openrouter.ai/api/v1/chat/completions",
                        "openai_like",
                    )
                if provider == "deepseek":
                    return "https://api.deepseek.com/v1/chat/completions", "openai_like"
                if provider == "siliconflow":
                    return (
                        "https://api.siliconflow.cn/v1/chat/completions",
                        "openai_like",
                    )
                if provider == "dashscope":
                    return (
                        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                        "openai_like",
                    )
                if provider == "openai-compatible":
                    if base_url:
                        bu = _normalize_base_url(base_url)
                        if bu.endswith("/v1"):
                            return f"{bu}/chat/completions", "openai_like"
                        return f"{bu}/v1/chat/completions", "openai_like"
                return None, "openai_like"

            # Decide endpoint for known OpenAI-compatible providers
            completed_via_direct = False
            try:
                if not api_key:
                    # Missing API key: fail fast for providers requiring auth
                    if provider in {
                        "openai",
                        "openrouter",
                        "deepseek",
                        "siliconflow",
                        "azure",
                        "google",
                    }:
                        result.ok = False
                        result.status = "auth_failed"
                        result.error = "API key is missing"
                        return SuccessResponse.create(data=result, msg="Auth failed")

                endpoint, style = _resolve_endpoint()

                if endpoint:
                    # Perform direct ping with timeout
                    if style == "google":
                        completed_via_direct = await asyncio.wait_for(
                            _direct_google_ping(endpoint), timeout=direct_timeout_s
                        )
                        # If 404 from v1beta, try v1 (or vice versa)
                        if (
                            not completed_via_direct
                            and (result.error or "").find("404") != -1
                        ):
                            alt_endpoint = None
                            if "/v1beta/" in endpoint:
                                alt_endpoint = endpoint.replace("/v1beta/", "/v1/")
                            elif "/v1/" in endpoint:
                                alt_endpoint = endpoint.replace("/v1/", "/v1beta/")
                            if alt_endpoint:
                                # Reset status/error before retry
                                result.status = None
                                result.error = None
                                completed_via_direct = await asyncio.wait_for(
                                    _direct_google_ping(alt_endpoint),
                                    timeout=direct_timeout_s,
                                )
                    else:
                        completed_via_direct = await asyncio.wait_for(
                            _direct_openai_like_ping(endpoint), timeout=direct_timeout_s
                        )
                    if completed_via_direct:
                        return SuccessResponse.create(
                            data=result, msg="Model reachable"
                        )
                    else:
                        return SuccessResponse.create(
                            data=result, msg=result.status or "Request failed"
                        )
                else:
                    # No endpoint available for direct probe
                    result.ok = False
                    result.status = "probe_unavailable"
                    if style == "azure":
                        result.error = "Azure requires API Host (base_url) and api_version for direct probe"
                    elif provider == "openai-compatible" and not base_url:
                        result.error = "OpenAI-compatible provider requires API Host to run direct probe"
                    else:
                        result.error = "Direct probe endpoint not resolved"
                    return SuccessResponse.create(data=result, msg="Probe unavailable")
            except asyncio.TimeoutError:
                result.ok = False
                result.status = "timeout"
                result.error = f"Timed out after {int(direct_timeout_s * 1000)} ms"
                return SuccessResponse.create(data=result, msg="Timeout")
            except httpx.TimeoutException:
                result.ok = False
                result.status = "timeout"
                result.error = f"Timed out after {int(direct_timeout_s * 1000)} ms"
                return SuccessResponse.create(data=result, msg="Timeout")
            except Exception as e:
                # Direct probe threw an unexpected error; report and do not fall back to agent
                result.ok = False
                result.status = "request_failed"
                result.error = str(e)
                return SuccessResponse.create(data=result, msg="Request failed")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to check model: {e}")

    @router.post(
        "/validate",
        response_model=SuccessResponse[CheckModelResponse],
        summary="Validate model with structured diagnostics",
        description=(
            "Structured model validation suitable for UI diagnostics. "
            "Includes staged checks and optional live reachability probe."
        ),
    )
    async def validate_model(
        payload: CheckModelRequest,
    ) -> SuccessResponse[CheckModelResponse]:
        return await check_model(payload)

    return router
