from linx.grpc import saas_agent_pb2
from linx.grpc_server import AgentBridgeServicer


def test_get_app_config():
    """Testa o método GetAppConfig."""
    servicer = AgentBridgeServicer()
    request = saas_agent_pb2.AppId(app_id="my-app")
    context = None

    response = servicer.GetAppConfig(request, context)

    assert response.db_host == "localhost"
    assert response.db_port == 5432
    assert response.mqtt_topic == "application/my-app/device/+/event/up"
