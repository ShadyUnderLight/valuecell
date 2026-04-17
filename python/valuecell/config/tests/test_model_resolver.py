from pathlib import Path

from valuecell.config.model_resolver import ModelResolver


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
    metadata:
      legacy_ids:
        - gpt-5
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


def test_resolve_canonical_ref(tmp_path: Path) -> None:
    _prepare_config(tmp_path)
    resolver = ModelResolver.from_config(config_dir=tmp_path)

    resolved = resolver.resolve("OpenAI/GPT-5.4")

    assert resolved is not None
    assert resolved.entry.ref == "openai/gpt-5.4"
    assert resolved.match_type == "canonical_ref"


def test_resolve_alias(tmp_path: Path) -> None:
    _prepare_config(tmp_path)
    resolver = ModelResolver.from_config(config_dir=tmp_path)

    resolved = resolver.resolve("gpt54")

    assert resolved is not None
    assert resolved.entry.ref == "openai/gpt-5.4"
    assert resolved.match_type == "alias"


def test_resolve_native_id(tmp_path: Path) -> None:
    _prepare_config(tmp_path)
    resolver = ModelResolver.from_config(config_dir=tmp_path)

    resolved = resolver.resolve("gpt-5-2025-08-07")

    assert resolved is not None
    assert resolved.entry.ref == "openai/gpt-5.4"
    assert resolved.match_type == "native_id"


def test_resolve_legacy_id_from_provider_compatibility(tmp_path: Path) -> None:
    _prepare_config(tmp_path)
    resolver = ModelResolver.from_config(config_dir=tmp_path)

    resolved = resolver.resolve("gpt-5")

    assert resolved is not None
    assert resolved.entry.ref == "openai/gpt-5.4"
    assert resolved.match_type == "legacy_id"
