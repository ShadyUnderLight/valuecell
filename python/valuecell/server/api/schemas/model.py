"""Model-related API schemas."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class LLMModelConfigData(BaseModel):
    """LLM model configuration used by frontend to prefill UserRequest.

    This is a relaxed version of agents.strategy_agent.models.LLMModelConfig,
    allowing `api_key` to be optional so the API can return defaults
    even when user credentials are not provided.
    """

    provider: str = Field(
        ..., description="Model provider, e.g. 'openrouter', 'google', 'openai'"
    )
    model_id: str = Field(
        ...,
        description="Model identifier, e.g. 'gpt-4o' or 'deepseek-ai/deepseek-v3.1'",
    )
    api_key: Optional[str] = Field(
        default=None, description="API key for the model provider (may be omitted)"
    )


# Extended provider and model management schemas
class ModelItem(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    model_name: Optional[str] = Field(None, description="Display name of the model")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata for the model"
    )


class ModelProviderSummary(BaseModel):
    provider: str = Field(..., description="Provider key, e.g. 'openrouter'")


class ProviderModelEntry(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    model_name: Optional[str] = Field(None, description="Display name of the model")


class ProviderDetailData(BaseModel):
    api_key: Optional[str] = Field(None, description="API key if available")
    base_url: Optional[str] = Field(None, description="API base URL")
    is_default: bool = Field(..., description="Whether this is the primary provider")
    default_model_id: Optional[str] = Field(
        None,
        description=(
            "Provider-native default model id used by the settings UI and "
            "default-model mutation endpoints"
        ),
    )
    default_model_ref: Optional[str] = Field(
        None,
        description=(
            "Canonical default model ref when the provider config exposes a "
            "shared cross-provider model-selection contract"
        ),
    )
    recommended_model_refs: List[str] = Field(
        default_factory=list,
        description=(
            "Canonical recommended model refs for shared provider/model selection"
        ),
    )
    api_key_url: Optional[str] = Field(
        None, description="URL to obtain/apply for the provider's API key"
    )
    models: List[ProviderModelEntry] = Field(
        default_factory=list, description="Available provider models"
    )


class ProviderUpdateRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="New API key to set for provider")
    base_url: Optional[str] = Field(
        None, description="New API base URL to set for provider"
    )


class AddModelRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier to add")
    model_name: Optional[str] = Field(None, description="Optional display name")


class ProviderValidateResponse(BaseModel):
    is_valid: bool = Field(..., description="Validation result")
    error: Optional[str] = Field(None, description="Error message if invalid")


class SetDefaultProviderRequest(BaseModel):
    provider: str = Field(..., description="Provider key to set as default")


class SetDefaultModelRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier to set as default")
    model_name: Optional[str] = Field(
        None,
        description="Optional display name; added/updated in models list if provided",
    )


# --- Model availability check ---
class CheckModelRequest(BaseModel):
    """Request payload to check if a provider+model is usable."""

    provider: Optional[str] = Field(
        None, description="Provider to check; defaults to current primary provider"
    )
    model_id: Optional[str] = Field(
        None, description="Model id to check; defaults to provider's default model"
    )
    model_ref: Optional[str] = Field(
        None, description="Canonical model ref to check (preferred when available)"
    )
    api_key: Optional[str] = Field(
        None, description="Temporary API key to use for this check (optional)"
    )
    # strict/live check removed; this endpoint now validates configuration only.


class ModelValidationStages(BaseModel):
    """Structured validation stages for UI-friendly diagnostics."""

    catalog_known: bool = Field(False, description="Whether model exists in catalog")
    provider_enabled: bool = Field(
        False, description="Whether provider is enabled in configuration"
    )
    provider_configured: bool = Field(
        False, description="Whether provider credentials/configuration are ready"
    )
    resolved: bool = Field(
        False, description="Whether input resolved to a canonical catalog entry"
    )
    native_model_id_present: bool = Field(
        False, description="Whether a provider-native model id is available"
    )
    reachable: bool = Field(
        False, description="Whether live provider probe reached the model endpoint"
    )
    deprecated: bool = Field(
        False, description="Whether resolved model is marked deprecated"
    )
    preview: bool = Field(False, description="Whether resolved model is preview/beta")


class CheckModelResponse(BaseModel):
    """Response payload describing the model availability check result."""

    ok: bool = Field(..., description="Whether the provider+model is usable")
    provider: str = Field(..., description="Provider under test")
    model_id: str = Field(..., description="Model id under test")
    status: Optional[str] = Field(
        None,
        description="Status label like 'valid_config', 'reachable', 'timeout', 'request_failed'",
    )
    error: Optional[str] = Field(None, description="Error message if any")
    canonical_ref: Optional[str] = Field(
        None, description="Resolved canonical model ref when available"
    )
    resolved_provider: Optional[str] = Field(
        None, description="Resolved provider when catalog resolution succeeds"
    )
    resolved_model_id: Optional[str] = Field(
        None, description="Resolved provider-native model id when available"
    )
    match_type: Optional[
        Literal["canonical_ref", "alias", "native_id", "legacy_id"]
    ] = Field(None, description="Catalog resolver match type when available")
    stages: ModelValidationStages = Field(
        default_factory=ModelValidationStages,
        description="Structured validation stages for UI consumption",
    )


class CatalogModelItem(BaseModel):
    canonical_ref: str = Field(..., description="Canonical catalog ref")
    provider: str = Field(..., description="Model provider")
    native_model_id: str = Field(..., description="Provider-native model id")
    display_name: str = Field(..., description="Display name")
    status: Optional[str] = Field(None, description="Catalog status")
    visibility: Optional[str] = Field(None, description="Catalog visibility")


class ResolveModelRequest(BaseModel):
    model: str = Field(..., description="Model identifier to resolve")
    provider: Optional[str] = Field(
        None, description="Optional provider hint to narrow resolution"
    )


class ResolveModelResponse(BaseModel):
    canonical_ref: str = Field(..., description="Canonical catalog ref")
    provider: str = Field(..., description="Resolved provider")
    native_model_id: str = Field(..., description="Resolved provider-native model id")
    display_name: str = Field(..., description="Resolved display name")
    match_type: Literal["canonical_ref", "alias", "native_id", "legacy_id"] = Field(
        ..., description="How the resolver matched the input"
    )


class ScanCandidateItem(BaseModel):
    model_id: str = Field(..., description="Provider-native model id")
    model_name: Optional[str] = Field(None, description="Provider model name")
    catalog_ref: Optional[str] = Field(
        None, description="Matched catalog ref if candidate already exists"
    )
    catalog_status: Optional[str] = Field(
        None, description="Matched catalog status if candidate already exists"
    )


class ScanDiffReport(BaseModel):
    new_model_ids: List[str] = Field(
        default_factory=list, description="Scanned ids not currently in catalog"
    )
    missing_model_ids: List[str] = Field(
        default_factory=list, description="Catalog ids not present in current scan"
    )
    renamed_model_ids: List[str] = Field(
        default_factory=list,
        description="Scanned ids whose names differ from catalog display names",
    )
    deprecated_model_ids: List[str] = Field(
        default_factory=list, description="Scanned ids marked deprecated in catalog"
    )


class ProviderScanResponse(BaseModel):
    provider: str = Field(..., description="Provider key")
    scanned_at: str = Field(..., description="UTC scan timestamp in ISO-8601 format")
    candidates: List[ScanCandidateItem] = Field(
        default_factory=list, description="Scanned provider candidates"
    )
    report: ScanDiffReport = Field(
        default_factory=ScanDiffReport, description="Scan diff report against catalog"
    )


class CatalogImportRequest(BaseModel):
    provider: str = Field(..., description="Provider key for this import")
    model_ids: List[str] = Field(
        default_factory=list, description="Scanned model ids selected for import"
    )


class CatalogImportItem(BaseModel):
    canonical_ref: str = Field(..., description="Canonical catalog ref")
    provider: str = Field(..., description="Provider key")
    native_model_id: str = Field(..., description="Provider-native model id")
    display_name: str = Field(..., description="Catalog display name")
    source: Literal["imported"] = Field(..., description="Catalog source marker")


class CatalogImportResponse(BaseModel):
    provider: str = Field(..., description="Provider key")
    imported: List[CatalogImportItem] = Field(
        default_factory=list, description="Imported catalog entries"
    )
    skipped_existing_model_ids: List[str] = Field(
        default_factory=list,
        description="Selected model ids already present in catalog",
    )
    missing_from_scan_model_ids: List[str] = Field(
        default_factory=list,
        description="Selected model ids that were not found in latest scan state",
    )
