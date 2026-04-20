from pathlib import Path

from valuecell.config.loader import ConfigLoader
from valuecell.config.manager import ConfigManager


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_base_config(tmp_path: Path, primary_provider: str = "openai") -> None:
    _write(
        tmp_path / "config.yaml",
        f"""
models:
  primary_provider: {primary_provider}
""",
    )


def test_config_health_reports_error_for_missing_primary_provider_credentials(
    tmp_path: Path,
) -> None:
    _write_base_config(tmp_path, primary_provider="openai")
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
connection:
  api_key_env: OPENAI_API_KEY
default_model: gpt-5
""",
    )

    report = ConfigManager(loader=ConfigLoader(config_dir=tmp_path)).get_config_health()

    assert report.status == "error"
    assert report.primary_provider == "openai"
    assert report.enabled_providers == []
    assert report.issues[0].scope == "provider:openai"
    assert "OPENAI_API_KEY" in report.issues[0].message


def test_config_health_reports_healthy_when_primary_provider_is_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_base_config(tmp_path, primary_provider="openai")
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
connection:
  api_key_env: OPENAI_API_KEY
default_model: gpt-5
""",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    report = ConfigManager(loader=ConfigLoader(config_dir=tmp_path)).get_config_health()

    assert report.status == "healthy"
    assert report.primary_provider == "openai"
    assert report.enabled_providers == ["openai"]
    assert report.issues == []


def test_config_health_adds_provider_inventory_warning_when_primary_credentials_are_missing(
    tmp_path: Path,
) -> None:
    _write_base_config(tmp_path, primary_provider="openai")
    _write(
        tmp_path / "providers" / "openai.yaml",
        """
connection:
  api_key_env: OPENAI_API_KEY
default_model: gpt-5
""",
    )

    report = ConfigManager(loader=ConfigLoader(config_dir=tmp_path)).get_config_health()

    assert report.status == "error"
    assert report.primary_provider == "openai"
    assert report.enabled_providers == []
    assert len(report.issues) == 2
    assert report.issues[0].level == "error"
    assert report.issues[0].scope == "provider:openai"
    assert "OPENAI_API_KEY" in report.issues[0].message
    assert report.issues[1].level == "warning"
    assert report.issues[1].scope == "providers"
    assert (
        report.issues[1].message
        == "No enabled providers with valid credentials were detected."
    )


def test_config_health_reports_missing_primary_provider_config_as_error(
    tmp_path: Path,
) -> None:
    _write_base_config(tmp_path, primary_provider="openai")

    report = ConfigManager(loader=ConfigLoader(config_dir=tmp_path)).get_config_health()

    assert report.status == "error"
    assert report.primary_provider == "openai"
    assert report.enabled_providers == []
    assert report.issues[0].level == "error"
    assert report.issues[0].scope == "provider:openai"
    assert "not found in configuration" in report.issues[0].message
    assert report.issues[1].level == "warning"
    assert report.issues[1].scope == "providers"
    assert (
        report.issues[1].message
        == "No enabled providers with valid credentials were detected."
    )
