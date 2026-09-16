from agent.config import AgentSettings


def test_settings_have_no_app_id():
    settings = AgentSettings()
    assert not hasattr(settings, "app_id")
    assert settings.saas_grpc_host == "localhost:50051"
    assert settings.config_cache_ttl_seconds == 60.0
