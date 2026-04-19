from pathlib import Path

from valuecell.config.loader import ConfigLoader
from valuecell.config.manager import ConfigManager


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_base_config(tmp_path: Path) -> None:
    _write(
        tmp_path / "config.yaml",
        """
models:
  primary_provider: openai
""",
    )


def test_get_provider_config_prefers_recommended_models(tmp_path: Path) -> None:
    _write_base_config(tmp_path)
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
default_model_ref: " openai/gpt-5.4 "
default_model: gpt-5
recommended_models:
  - openai/gpt-5.4
  - openai/gpt-4.1
models:
  - id: gpt-5
    name: GPT-5 Legacy
  - id: gpt-4.1-legacy
    name: GPT-4.1 Legacy
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
  - ref: openai/gpt-4.1
    provider: openai
    native_model_id: gpt-4.1-2025-04-14
    display_name: GPT-4.1
""",
    )

    manager = ConfigManager(loader=ConfigLoader(config_dir=tmp_path))
    config = manager.get_provider_config("openai")

    assert config is not None
    assert config.default_model == "gpt-5"
    assert config.default_model_ref == "openai/gpt-5.4"
    assert config.recommended_models == ["openai/gpt-5.4", "openai/gpt-4.1"]
    assert config.models == [
        {"id": "gpt-5-2025-08-07", "name": "GPT-5.4"},
        {"id": "gpt-4.1-2025-04-14", "name": "GPT-4.1"},
        {"id": "gpt-5", "name": "GPT-5 Legacy"},
        {"id": "gpt-4.1-legacy", "name": "GPT-4.1 Legacy"},
    ]


def test_get_provider_config_keeps_legacy_models_when_no_recommended(
    tmp_path: Path,
) -> None:
    _write_base_config(tmp_path)
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
default_model: gpt-5
models:
  - id: gpt-5
    name: GPT-5 Legacy
""",
    )

    manager = ConfigManager(loader=ConfigLoader(config_dir=tmp_path))
    config = manager.get_provider_config("openai")

    assert config is not None
    assert config.default_model_ref is None
    assert config.recommended_models == []
    assert config.models == [{"id": "gpt-5", "name": "GPT-5 Legacy"}]


def test_get_provider_config_keeps_uncovered_legacy_models_after_recommended(
    tmp_path: Path,
) -> None:
    _write_base_config(tmp_path)
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
recommended_models:
  - openai/gpt-5.4
models:
  - id: gpt-5
    name: GPT-5 Legacy
  - id: gpt-4.1-legacy
    name: GPT-4.1 Legacy
  - id: custom-local-model
    name: Custom Local Model
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
""",
    )

    manager = ConfigManager(loader=ConfigLoader(config_dir=tmp_path))
    config = manager.get_provider_config("openai")

    assert config is not None
    assert config.models == [
        {"id": "gpt-5-2025-08-07", "name": "GPT-5.4"},
        {"id": "gpt-5", "name": "GPT-5 Legacy"},
        {"id": "gpt-4.1-legacy", "name": "GPT-4.1 Legacy"},
        {"id": "custom-local-model", "name": "Custom Local Model"},
    ]


def test_get_provider_config_supports_minimax_cn(tmp_path: Path, monkeypatch) -> None:
    _write_base_config(tmp_path)
    _write(
        tmp_path / "providers" / "minimax_cn.yaml",
        """
connection:
  base_url: https://api.minimaxi.com/v1
  api_key_env: MINIMAX_CN_API_KEY
default_model_ref: minimax_cn/minimax-m2.7
default_model: MiniMax-M2.7
recommended_models:
  - minimax_cn/minimax-m2.7
models:
  - id: MiniMax-M2.7
    name: MiniMax CN Legacy
""",
    )
    _write(
        tmp_path / "models" / "catalog" / "minimax_cn.yaml",
        """
entries:
  - ref: minimax_cn/minimax-m2.7
    provider: minimax_cn
    native_model_id: MiniMax-M2.7
    display_name: MiniMax CN M2.7
""",
    )
    monkeypatch.setenv("MINIMAX_CN_API_KEY", "test-minimax-cn-key")

    manager = ConfigManager(loader=ConfigLoader(config_dir=tmp_path))
    config = manager.get_provider_config("minimax_cn")

    assert config is not None
    assert config.base_url == "https://api.minimaxi.com/v1"
    assert config.api_key == "test-minimax-cn-key"
    assert config.default_model_ref == "minimax_cn/minimax-m2.7"
    assert config.models[0] == {"id": "MiniMax-M2.7", "name": "MiniMax CN M2.7"}
