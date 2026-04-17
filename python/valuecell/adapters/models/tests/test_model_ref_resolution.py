from pathlib import Path

from valuecell.adapters.models.factory import ModelFactory
from valuecell.config.loader import ConfigLoader
from valuecell.config.manager import ConfigManager


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_config(tmp_path: Path) -> ConfigManager:
    _write(
        tmp_path / "config.yaml",
        """
models:
  primary_provider: openai
""",
    )
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
enabled: true
connection:
  api_key_env: OPENAI_API_KEY
default_model_ref: openai/gpt-5.4
default_model: gpt-5
models:
  - id: gpt-5
    name: GPT-5 Legacy
defaults: {}
""",
    )
    _write(
        tmp_path / "models" / "catalog" / "openai.yaml",
        """
entries:
  - ref: openai/gpt-5.4
    provider: openai
    native_model_id: gpt-5-2025-08-07
    display_name: GPT-5.4
    metadata:
      legacy_ids:
        - gpt-5
""",
    )
    loader = ConfigLoader(config_dir=tmp_path)
    return ConfigManager(loader=loader)


def test_create_model_prefers_explicit_model_ref(
    tmp_path: Path, monkeypatch
) -> None:
    manager = _prepare_config(tmp_path)
    factory = ModelFactory(config_manager=manager)
    monkeypatch.setattr(
        factory,
        "_create_model_internal",
        lambda model_id, provider, **kwargs: {
            "provider": provider,
            "model_id": model_id,
        },
    )

    result = factory.create_model(
        provider="openai",
        model_ref="openai/gpt-5.4",
        model_id="gpt-5",
        use_fallback=False,
    )

    assert result["provider"] == "openai"
    assert result["model_id"] == "gpt-5-2025-08-07"


def test_create_model_keeps_legacy_explicit_model_id(
    tmp_path: Path, monkeypatch
) -> None:
    manager = _prepare_config(tmp_path)
    factory = ModelFactory(config_manager=manager)
    monkeypatch.setattr(
        factory,
        "_create_model_internal",
        lambda model_id, provider, **kwargs: {
            "provider": provider,
            "model_id": model_id,
        },
    )

    result = factory.create_model(
        provider="openai",
        model_id="gpt-5",
        use_fallback=False,
    )

    assert result["provider"] == "openai"
    assert result["model_id"] == "gpt-5"


def test_create_model_uses_provider_default_model_ref(
    tmp_path: Path, monkeypatch
) -> None:
    manager = _prepare_config(tmp_path)
    factory = ModelFactory(config_manager=manager)
    monkeypatch.setattr(
        factory,
        "_create_model_internal",
        lambda model_id, provider, **kwargs: {
            "provider": provider,
            "model_id": model_id,
        },
    )

    result = factory.create_model(
        provider="openai",
        use_fallback=False,
    )

    assert result["provider"] == "openai"
    assert result["model_id"] == "gpt-5-2025-08-07"
