"""Configuration schema/version domains for ValueCell."""

from dataclasses import dataclass
from typing import Dict, Literal


@dataclass(frozen=True)
class ConfigVersionDomain:
    """Single configuration evolution domain."""

    domain: str
    owner: Literal["frontend", "backend"]
    schema_key: str
    versioning_mode: Literal["explicit", "normalized-contract"]
    current_version: int | None
    notes: str


CONFIG_VERSION_DOMAINS: Dict[str, ConfigVersionDomain] = {
    "frontend.persist.settings": ConfigVersionDomain(
        domain="frontend.persist.settings",
        owner="frontend",
        schema_key="valuecell-settings",
        versioning_mode="explicit",
        current_version=1,
        notes="Zustand persisted settings store; migrations are gated by persist version metadata.",
    ),
    "frontend.persist.system": ConfigVersionDomain(
        domain="frontend.persist.system",
        owner="frontend",
        schema_key="valuecell-system-store",
        versioning_mode="explicit",
        current_version=1,
        notes="Zustand persisted system/auth store; sanitizes malformed snapshots at load time.",
    ),
    "backend.runtime.config-health": ConfigVersionDomain(
        domain="backend.runtime.config-health",
        owner="backend",
        schema_key="system.config-health",
        versioning_mode="normalized-contract",
        current_version=None,
        notes="Runtime config health summary contract exposed via /api/v1/system/config-health.",
    ),
    "backend.config.provider": ConfigVersionDomain(
        domain="backend.config.provider",
        owner="backend",
        schema_key="providers/*.yaml",
        versioning_mode="normalized-contract",
        current_version=None,
        notes="Provider YAML config keeps legacy fields but normalizes default_model_ref and recommended_models on load.",
    ),
    "backend.config.agent": ConfigVersionDomain(
        domain="backend.config.agent",
        owner="backend",
        schema_key="agents/*.yaml",
        versioning_mode="normalized-contract",
        current_version=None,
        notes="Agent YAML config resolves via loader merge rules and env_overrides instead of explicit schema version fields.",
    ),
}
