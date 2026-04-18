"""Provider-facing model inventory source for scan workflow.

This module is intentionally decoupled from curated provider YAML model lists.
It provides a minimal adapter boundary so scan can later switch to real provider APIs
without changing router logic.
"""

from dataclasses import dataclass
from typing import Dict, Protocol, Sequence


@dataclass(frozen=True)
class ProviderInventoryModel:
    """Single model candidate discovered from a provider-facing inventory source."""

    model_id: str
    model_name: str | None = None


class ProviderInventorySource(Protocol):
    """Abstraction for fetching provider model inventories."""

    async def list_models(self, provider: str) -> list[ProviderInventoryModel]:
        """Return provider-facing model inventory candidates for the given provider."""


_STUB_PROVIDER_INVENTORY: Dict[str, Sequence[ProviderInventoryModel]] = {
    # Provider-specific stub values for local development and tests.
    "openai": (
        ProviderInventoryModel(model_id="gpt-5-2025-08-07", model_name="GPT-5.4"),
        ProviderInventoryModel(
            model_id="gpt-5-mini-2025-08-07", model_name="GPT-5.4 Mini"
        ),
    ),
    "google": (
        ProviderInventoryModel(
            model_id="gemini-2.5-flash", model_name="Gemini 2.5 Flash"
        ),
    ),
    "openrouter": (
        ProviderInventoryModel(model_id="openai/gpt-5", model_name="GPT-5"),
        ProviderInventoryModel(
            model_id="google/gemini-2.5-flash", model_name="Gemini 2.5 Flash"
        ),
    ),
}


class StubProviderInventorySource:
    """Provider inventory source backed by static provider-specific stubs."""

    def __init__(
        self, inventory: Dict[str, Sequence[ProviderInventoryModel]] | None = None
    ) -> None:
        self._inventory = _STUB_PROVIDER_INVENTORY if inventory is None else inventory

    async def list_models(self, provider: str) -> list[ProviderInventoryModel]:
        models = self._inventory.get(provider, ())
        return [
            ProviderInventoryModel(model_id=item.model_id, model_name=item.model_name)
            for item in models
        ]


_provider_inventory_source: ProviderInventorySource | None = None


def get_provider_inventory_source() -> ProviderInventorySource:
    """Return the active provider inventory source.

    Defaults to a provider-specific stub source until live provider API adapters are added.
    """
    global _provider_inventory_source
    if _provider_inventory_source is None:
        _provider_inventory_source = StubProviderInventorySource()
    return _provider_inventory_source
