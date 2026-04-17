"""Model catalog resolver utilities.

This module resolves user-facing model identifiers into canonical model catalog entries.
Resolution supports canonical refs, aliases, provider-native ids, and legacy ids.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Literal, Optional

from valuecell.config.loader import ConfigLoader
from valuecell.config.model_catalog import (
    ModelCatalog,
    ModelCatalogEntry,
    ModelCatalogLoader,
)


MatchType = Literal["canonical_ref", "alias", "native_id", "legacy_id"]


def _normalize_key(value: str) -> str:
    return value.strip().lower()


@dataclass(frozen=True)
class ModelResolution:
    """Resolved canonical model entry with match type."""

    entry: ModelCatalogEntry
    match_type: MatchType


class ModelResolver:
    """Resolve model identifiers against the model catalog and legacy provider ids."""

    def __init__(
        self,
        catalog: ModelCatalog,
        legacy_model_ids_by_provider: Optional[Dict[str, set[str]]] = None,
    ) -> None:
        self.catalog = catalog
        self._legacy_model_ids_by_provider = legacy_model_ids_by_provider or {}

        self._entries_by_ref: Dict[str, ModelCatalogEntry] = {}
        self._entries_by_provider_alias: Dict[str, Dict[str, ModelCatalogEntry]] = {}
        self._entries_by_provider_native_id: Dict[str, Dict[str, ModelCatalogEntry]] = {}
        self._entries_by_provider_legacy_id: Dict[str, Dict[str, ModelCatalogEntry]] = {}

        self._build_indexes(catalog.entries)

    @classmethod
    def from_config(cls, config_dir: Optional[Path] = None) -> "ModelResolver":
        catalog_loader = ModelCatalogLoader(config_dir=config_dir)
        catalog = catalog_loader.load()

        legacy_ids = cls._load_legacy_provider_model_ids(config_dir=config_dir)
        return cls(catalog=catalog, legacy_model_ids_by_provider=legacy_ids)

    @staticmethod
    def _load_legacy_provider_model_ids(
        config_dir: Optional[Path] = None,
    ) -> Dict[str, set[str]]:
        loader = ConfigLoader(config_dir=config_dir)
        ids_by_provider: Dict[str, set[str]] = {}

        for provider in loader.list_providers():
            provider_config = loader.load_provider_config(provider)
            provider_ids: set[str] = set()

            default_model = provider_config.get("default_model")
            if isinstance(default_model, str) and default_model.strip():
                provider_ids.add(_normalize_key(default_model))

            models = provider_config.get("models", [])
            if not isinstance(models, list):
                ids_by_provider[_normalize_key(provider)] = provider_ids
                continue

            for model in models:
                if not isinstance(model, dict):
                    continue
                model_id = model.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    provider_ids.add(_normalize_key(model_id))

            ids_by_provider[_normalize_key(provider)] = provider_ids

        return ids_by_provider

    def _build_indexes(self, entries: Iterable[ModelCatalogEntry]) -> None:
        for entry in entries:
            self._entries_by_ref[entry.normalized_ref] = entry

            provider_aliases = self._entries_by_provider_alias.setdefault(
                entry.provider, {}
            )
            for normalized_alias in entry.normalized_aliases:
                provider_aliases[normalized_alias] = entry

            provider_native_ids = self._entries_by_provider_native_id.setdefault(
                entry.provider, {}
            )
            provider_native_ids[_normalize_key(entry.native_model_id)] = entry

            provider_legacy_ids = self._entries_by_provider_legacy_id.setdefault(
                entry.provider, {}
            )
            for legacy_id in self._extract_legacy_ids(entry):
                provider_legacy_ids[_normalize_key(legacy_id)] = entry

    def _extract_legacy_ids(self, entry: ModelCatalogEntry) -> tuple[str, ...]:
        raw = entry.metadata.get("legacy_ids")
        if not isinstance(raw, list):
            return ()

        legacy_ids: list[str] = []
        for value in raw:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if normalized:
                legacy_ids.append(normalized)
        return tuple(legacy_ids)

    def resolve(
        self,
        identifier: str,
        provider: Optional[str] = None,
    ) -> Optional[ModelResolution]:
        if not isinstance(identifier, str):
            return None

        normalized_identifier = _normalize_key(identifier)
        if not normalized_identifier:
            return None

        normalized_provider = _normalize_key(provider) if provider else None

        ref_match = self._entries_by_ref.get(normalized_identifier)
        if ref_match is not None:
            if (
                normalized_provider is not None
                and ref_match.provider != normalized_provider
            ):
                return None
            return ModelResolution(entry=ref_match, match_type="canonical_ref")

        alias_match = self._resolve_provider_scoped_match(
            index=self._entries_by_provider_alias,
            identifier=normalized_identifier,
            provider=normalized_provider,
        )
        if alias_match is not None:
            return ModelResolution(entry=alias_match, match_type="alias")

        native_match = self._resolve_provider_scoped_match(
            index=self._entries_by_provider_native_id,
            identifier=normalized_identifier,
            provider=normalized_provider,
        )
        if native_match is not None:
            return ModelResolution(entry=native_match, match_type="native_id")

        legacy_match = self._resolve_legacy_match(
            identifier=normalized_identifier,
            provider=normalized_provider,
        )
        if legacy_match is not None:
            return ModelResolution(entry=legacy_match, match_type="legacy_id")

        return None

    def _resolve_provider_scoped_match(
        self,
        index: Dict[str, Dict[str, ModelCatalogEntry]],
        identifier: str,
        provider: Optional[str],
    ) -> Optional[ModelCatalogEntry]:
        if provider is not None:
            return index.get(provider, {}).get(identifier)

        matches: list[ModelCatalogEntry] = []
        for provider_index in index.values():
            entry = provider_index.get(identifier)
            if entry is not None:
                matches.append(entry)

        if len(matches) == 1:
            return matches[0]

        return None

    def _resolve_legacy_match(
        self,
        identifier: str,
        provider: Optional[str],
    ) -> Optional[ModelCatalogEntry]:
        providers: tuple[str, ...]
        if provider is not None:
            providers = (provider,)
        else:
            providers = tuple(self._legacy_model_ids_by_provider.keys())

        matches: list[ModelCatalogEntry] = []
        for provider_name in providers:
            legacy_ids = self._legacy_model_ids_by_provider.get(provider_name, set())
            if identifier not in legacy_ids:
                continue

            legacy_index = self._entries_by_provider_legacy_id.get(provider_name, {})
            matched_entry = legacy_index.get(identifier)
            if matched_entry is not None:
                matches.append(matched_entry)

        if len(matches) == 1:
            return matches[0]

        return None
