from valuecell.config.versioning import CONFIG_VERSION_DOMAINS


def test_config_version_domains_cover_frontend_persist_stores() -> None:
    settings = CONFIG_VERSION_DOMAINS["frontend.persist.settings"]
    system = CONFIG_VERSION_DOMAINS["frontend.persist.system"]

    assert settings.owner == "frontend"
    assert settings.schema_key == "valuecell-settings"
    assert settings.versioning_mode == "explicit"
    assert settings.current_version == 1

    assert system.owner == "frontend"
    assert system.schema_key == "valuecell-system-store"
    assert system.versioning_mode == "explicit"
    assert system.current_version == 1


def test_config_version_domains_capture_backend_normalized_contracts() -> None:
    provider = CONFIG_VERSION_DOMAINS["backend.config.provider"]
    agent = CONFIG_VERSION_DOMAINS["backend.config.agent"]
    config_health = CONFIG_VERSION_DOMAINS["backend.runtime.config-health"]

    assert provider.owner == "backend"
    assert provider.versioning_mode == "normalized-contract"
    assert provider.current_version is None
    assert "default_model_ref" in provider.notes

    assert agent.owner == "backend"
    assert agent.versioning_mode == "normalized-contract"
    assert agent.current_version is None
    assert "env_overrides" in agent.notes

    assert config_health.schema_key == "system.config-health"
    assert config_health.versioning_mode == "normalized-contract"
    assert config_health.current_version is None
