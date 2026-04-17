from pathlib import Path

import pytest

from valuecell.config.model_catalog import ModelCatalogLoader


def _write_catalog_file(base_dir: Path, filename: str, content: str) -> None:
    catalog_dir = base_dir / "models" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / filename).write_text(content, encoding="utf-8")


def test_load_model_catalog_valid(tmp_path: Path) -> None:
    _write_catalog_file(
        tmp_path,
        "openai.yaml",
        """
entries:
  - ref: OpenAI/GPT-5.4
    provider: OpenAI
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
    aliases: [GPT54, gpt-5.4]
    status: stable
    visibility: public
    metadata:
      family: gpt-5
""",
    )

    loader = ModelCatalogLoader(config_dir=tmp_path)
    catalog = loader.load()

    assert len(catalog.entries) == 1
    entry = catalog.entries[0]
    assert entry.ref == "OpenAI/GPT-5.4"
    assert entry.provider == "openai"
    assert entry.native_model_id == "gpt-5-2025-08-07"
    assert entry.display_name == "GPT-5.4"
    assert entry.aliases == ("GPT54", "gpt-5.4")
    assert entry.normalized_ref == "openai/gpt-5.4"
    assert entry.normalized_aliases == ("gpt54", "gpt-5.4")


def test_load_model_catalog_duplicate_refs_rejected(tmp_path: Path) -> None:
    _write_catalog_file(
        tmp_path,
        "provider_a.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: openai
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
""",
    )
    _write_catalog_file(
        tmp_path,
        "provider_b.yaml",
        """
entries:
  - ref: OpenAI/GPT-5.4
    provider: openai
    native_model_id: gpt-5-2025-09-01
    display_name: GPT-5.4 alt
""",
    )

    loader = ModelCatalogLoader(config_dir=tmp_path)

    with pytest.raises(ValueError, match="Duplicate model ref detected"):
        loader.load()


def test_load_model_catalog_duplicate_aliases_same_provider_rejected(
    tmp_path: Path,
) -> None:
    _write_catalog_file(
        tmp_path,
        "openai.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: openai
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
    aliases: [gpt54]
  - ref: openai/gpt-4.1
    provider: openai
    native_model_id: gpt-4.1-2025-04-14
    display_name: GPT-4.1
    aliases: [GPT54]
""",
    )

    loader = ModelCatalogLoader(config_dir=tmp_path)

    with pytest.raises(
        ValueError, match="Duplicate alias detected within provider scope"
    ):
        loader.load()


def test_load_model_catalog_malformed_entry_rejected(tmp_path: Path) -> None:
    _write_catalog_file(
        tmp_path,
        "openai.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: openai
    display_name: GPT-5.4
""",
    )

    loader = ModelCatalogLoader(config_dir=tmp_path)

    with pytest.raises(ValueError, match="Malformed catalog entry"):
        loader.load()


def test_load_model_catalog_ref_provider_mismatch_rejected(tmp_path: Path) -> None:
    _write_catalog_file(
        tmp_path,
        "openai.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: deepseek
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
""",
    )

    loader = ModelCatalogLoader(config_dir=tmp_path)

    with pytest.raises(ValueError, match="ref/provider mismatch"):
        loader.load()


def test_load_model_catalog_invalid_yaml_rejected(tmp_path: Path) -> None:
    _write_catalog_file(
        tmp_path,
        "openai.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: openai
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
    aliases: [gpt54, gpt-5.4
""",
    )

    loader = ModelCatalogLoader(config_dir=tmp_path)

    with pytest.raises(ValueError, match="Malformed catalog file .*invalid YAML"):
        loader.load()
