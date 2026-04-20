"""Model catalog schema and loader.

This module provides:
- pydantic schema validation for model catalog entries
- normalized backend types for runtime-safe access
- a loader that reads catalog YAML files from repo config path
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from yaml import YAMLError

from valuecell.config.constants import CONFIG_DIR


DEFAULT_MODEL_CATALOG_DIR = Path("models") / "catalog"


def _normalize_key(value: str) -> str:
    """Normalize keys used for matching and de-duplication."""
    return value.strip().lower()


class ModelCatalogEntrySchema(BaseModel):
    """Single model catalog entry parsed from YAML."""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(..., description="Canonical catalog ref, e.g. openai/gpt-5.4")
    provider: str = Field(..., description="Provider key, e.g. openai")
    native_model_id: str = Field(..., description="Provider-native runtime model id")
    display_name: str = Field(..., description="UI-facing display name")
    aliases: List[str] = Field(default_factory=list)
    status: Optional[str] = None
    visibility: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "ref", "provider", "native_model_id", "display_name", mode="before"
    )
    @classmethod
    def _validate_required_non_empty(cls, value: Any) -> Any:
        if not isinstance(value, str):
            raise ValueError("must be a non-empty string")

        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")

        return stripped

    @field_validator("aliases", mode="before")
    @classmethod
    def _validate_aliases(cls, value: Any) -> Any:
        if value is None:
            return []

        if not isinstance(value, list):
            raise ValueError("must be a list")

        normalized_aliases: List[str] = []
        for alias in value:
            if not isinstance(alias, str):
                raise ValueError("must contain only strings")

            alias_value = alias.strip()
            if not alias_value:
                raise ValueError("must not contain empty strings")

            normalized_aliases.append(alias_value)

        return normalized_aliases

    @field_validator("metadata", mode="before")
    @classmethod
    def _validate_metadata(cls, value: Any) -> Any:
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise ValueError("must be an object")

        return value


@dataclass(frozen=True)
class ModelCatalogEntry:
    """Normalized backend representation of a catalog entry."""

    ref: str
    provider: str
    native_model_id: str
    display_name: str
    aliases: tuple[str, ...]
    status: Optional[str]
    visibility: Optional[str]
    metadata: Dict[str, Any]
    normalized_ref: str
    normalized_aliases: tuple[str, ...]

    @classmethod
    def from_schema(cls, schema: ModelCatalogEntrySchema) -> "ModelCatalogEntry":
        normalized_provider = _normalize_key(schema.provider)

        aliases = tuple(schema.aliases)
        normalized_aliases = tuple(_normalize_key(alias) for alias in aliases)

        return cls(
            ref=schema.ref,
            provider=normalized_provider,
            native_model_id=schema.native_model_id,
            display_name=schema.display_name,
            aliases=aliases,
            status=schema.status,
            visibility=schema.visibility,
            metadata=dict(schema.metadata),
            normalized_ref=_normalize_key(schema.ref),
            normalized_aliases=normalized_aliases,
        )


@dataclass(frozen=True)
class ModelCatalog:
    """Model catalog collection with helper indexes."""

    entries: tuple[ModelCatalogEntry, ...]


class ModelCatalogLoader:
    """Load and validate model catalog config files from repository configs."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir) if config_dir is not None else CONFIG_DIR

    def load(
        self, relative_catalog_dir: Path = DEFAULT_MODEL_CATALOG_DIR
    ) -> ModelCatalog:
        """Load and validate model catalog from YAML files.

        Args:
            relative_catalog_dir: relative path under config dir, default models/catalog

        Returns:
            Validated model catalog.
        """
        catalog_dir = self.config_dir / relative_catalog_dir
        if not catalog_dir.exists():
            return ModelCatalog(entries=())

        if not catalog_dir.is_dir():
            raise ValueError(f"Model catalog path is not a directory: {catalog_dir}")

        yaml_files = sorted(catalog_dir.glob("*.yaml"))
        entries: List[ModelCatalogEntry] = []

        for path in yaml_files:
            loaded_data = self._load_yaml(path)
            raw_entries = self._extract_entries(loaded_data, path)

            for index, raw_entry in enumerate(raw_entries):
                if not isinstance(raw_entry, dict):
                    raise ValueError(
                        f"Malformed catalog entry in {path} at index {index}: "
                        "each entry must be an object"
                    )

                try:
                    schema = ModelCatalogEntrySchema.model_validate(raw_entry)
                except ValidationError as exc:
                    raise ValueError(
                        f"Malformed catalog entry in {path} at index {index}: {exc}"
                    ) from exc

                entries.append(ModelCatalogEntry.from_schema(schema))

        self._validate_duplicates(entries)
        return ModelCatalog(entries=tuple(entries))

    def _load_yaml(self, path: Path) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file)
        except YAMLError as exc:
            raise ValueError(
                f"Malformed catalog file {path}: invalid YAML: {exc}"
            ) from exc

    def _extract_entries(self, loaded_data: Any, path: Path) -> List[Any]:
        if loaded_data is None:
            return []

        if isinstance(loaded_data, list):
            return loaded_data

        if isinstance(loaded_data, dict):
            entries = loaded_data.get("entries")
            if entries is not None:
                if not isinstance(entries, list):
                    raise ValueError(
                        f"Malformed catalog file {path}: 'entries' must be a list"
                    )
                return entries

            models = loaded_data.get("models")
            if models is not None:
                if not isinstance(models, list):
                    raise ValueError(
                        f"Malformed catalog file {path}: 'models' must be a list"
                    )
                return models

        raise ValueError(
            f"Malformed catalog file {path}: "
            "expected a list or object with 'entries'/'models'"
        )

    def _validate_duplicates(self, entries: List[ModelCatalogEntry]) -> None:
        seen_refs: Dict[str, str] = {}
        aliases_by_provider: Dict[str, Dict[str, str]] = {}

        for entry in entries:
            self._validate_ref_provider_consistency(entry)

            previous_ref = seen_refs.get(entry.normalized_ref)
            if previous_ref is not None:
                raise ValueError(
                    "Duplicate model ref detected: "
                    f"'{entry.ref}' conflicts with '{previous_ref}'"
                )
            seen_refs[entry.normalized_ref] = entry.ref

            provider_aliases = aliases_by_provider.setdefault(entry.provider, {})
            for alias, normalized_alias in zip(entry.aliases, entry.normalized_aliases):
                previous_alias = provider_aliases.get(normalized_alias)
                if previous_alias is not None:
                    raise ValueError(
                        "Duplicate alias detected within provider scope: "
                        f"provider='{entry.provider}', alias='{alias}' "
                        f"conflicts with '{previous_alias}'"
                    )
                provider_aliases[normalized_alias] = alias

    def _validate_ref_provider_consistency(self, entry: ModelCatalogEntry) -> None:
        if "/" not in entry.ref:
            raise ValueError(
                "Malformed catalog entry: ref must use 'provider/model' format: "
                f"ref='{entry.ref}'"
            )

        ref_provider, _, _ = entry.ref.partition("/")
        normalized_ref_provider = _normalize_key(ref_provider)
        if normalized_ref_provider != entry.provider:
            raise ValueError(
                "Malformed catalog entry: ref/provider mismatch: "
                f"ref='{entry.ref}', provider='{entry.provider}'"
            )


_catalog_loader: Optional[ModelCatalogLoader] = None


def get_model_catalog_loader() -> ModelCatalogLoader:
    """Get singleton model catalog loader."""
    global _catalog_loader
    if _catalog_loader is None:
        _catalog_loader = ModelCatalogLoader()
    return _catalog_loader
