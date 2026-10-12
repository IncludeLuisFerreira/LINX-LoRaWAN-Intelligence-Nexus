from unittest.mock import MagicMock

import grpc
import pytest
from chirpstack_api import api
from linx_shared.core.exceptions import ExternalServiceError

from identity_api.chirpstack_client import ChirpStackClient


class _FakeRpcError(grpc.RpcError):
    def details(self) -> str:
        return "device already exists"


def test_create_device_propagates_token_and_device(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)
    device = api.Device(dev_eui="1122334455667788", name="sensor-01")

    client.create_device(device)

    fake_stub.Create.assert_called_once()
    args, kwargs = fake_stub.Create.call_args
    assert args[0].device.dev_eui == "1122334455667788"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_channel_created_from_host_when_none_provided(monkeypatch):
    monkeypatch.setattr(grpc, "insecure_channel", MagicMock())

    ChirpStackClient("localhost:8080", "tok")

    grpc.insecure_channel.assert_called_once_with("localhost:8080")


def test_explicit_channel_avoids_creating_new_one(monkeypatch):
    fake_channel = MagicMock()
    monkeypatch.setattr(grpc, "insecure_channel", MagicMock())

    ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    grpc.insecure_channel.assert_not_called()


def test_create_device_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Create.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.create_device(api.Device(dev_eui="1122334455667788"))

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "create_device"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)


def test_delete_device_propagates_dev_eui_and_token(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.delete_device("1122334455667788")

    fake_stub.Delete.assert_called_once()
    args, kwargs = fake_stub.Delete.call_args
    assert args[0].dev_eui == "1122334455667788"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_delete_device_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Delete.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.delete_device("1122334455667788")

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "delete_device"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)


def test_create_device_keys_propagates_dev_eui_app_key_and_token(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.create_device_keys(
        "1122334455667788", "00112233445566778899aabbccddeeff"
    )

    fake_stub.CreateKeys.assert_called_once()
    args, kwargs = fake_stub.CreateKeys.call_args
    assert args[0].device_keys.dev_eui == "1122334455667788"
    assert args[0].device_keys.nwk_key == "00112233445566778899aabbccddeeff"
    assert args[0].device_keys.app_key == "00112233445566778899aabbccddeeff"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_create_device_keys_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.CreateKeys.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.create_device_keys(
            "1122334455667788", "00112233445566778899aabbccddeeff"
        )

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "create_device_keys"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)


def test_list_device_profiles_sends_tenant_id_and_returns_items(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.List.return_value = api.ListDeviceProfilesResponse(
        result=[
            api.DeviceProfileListItem(id="p1", name="profile-1"),
            api.DeviceProfileListItem(id="p2", name="profile-2"),
        ],
        total_count=2,
    )
    monkeypatch.setattr(
        api, "DeviceProfileServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    profiles = client.list_device_profiles("tenant-abc")

    fake_stub.List.assert_called_once()
    args, kwargs = fake_stub.List.call_args
    assert args[0].tenant_id == "tenant-abc"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]
    assert [p.id for p in profiles] == ["p1", "p2"]


def test_list_device_profiles_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.List.side_effect = _FakeRpcError()
    monkeypatch.setattr(
        api, "DeviceProfileServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.list_device_profiles("tenant-abc")

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "list_device_profiles"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)


def test_list_device_profiles_grows_limit_until_complete(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()

    def items(count: int) -> list[api.DeviceProfileListItem]:
        return [
            api.DeviceProfileListItem(id=f"p{index}", name=f"p{index}")
            for index in range(count)
        ]

    fake_stub.List.side_effect = [
        api.ListDeviceProfilesResponse(result=items(100), total_count=150),
        api.ListDeviceProfilesResponse(result=items(150), total_count=150),
    ]
    monkeypatch.setattr(
        api, "DeviceProfileServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    profiles = client.list_device_profiles("tenant-abc")

    assert len(profiles) == 150
    assert fake_stub.List.call_count == 2
    first_request = fake_stub.List.call_args_list[0].args[0]
    second_request = fake_stub.List.call_args_list[1].args[0]
    assert first_request.limit == 100
    assert second_request.limit == 200
    assert second_request.offset == 0


def test_close_closes_channel():
    fake_channel = MagicMock()

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)
    client.close()

    fake_channel.close.assert_called_once()


def test_tls_enabled_uses_secure_channel(monkeypatch):
    credentials = MagicMock()
    monkeypatch.setattr(
        grpc, "ssl_channel_credentials", MagicMock(return_value=credentials)
    )
    monkeypatch.setattr(grpc, "secure_channel", MagicMock())
    monkeypatch.setattr(grpc, "insecure_channel", MagicMock())

    ChirpStackClient("chirpstack:8080", "tok", use_tls=True)

    grpc.ssl_channel_credentials.assert_called_once_with(
        root_certificates=None
    )
    grpc.secure_channel.assert_called_once_with("chirpstack:8080", credentials)
    grpc.insecure_channel.assert_not_called()


def test_tls_reads_ca_cert_file(monkeypatch, tmp_path):
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_bytes(b"CERT")
    credentials = MagicMock()
    monkeypatch.setattr(
        grpc, "ssl_channel_credentials", MagicMock(return_value=credentials)
    )
    monkeypatch.setattr(grpc, "secure_channel", MagicMock())

    ChirpStackClient(
        "chirpstack:8080", "tok", use_tls=True, ca_cert=str(ca_cert)
    )

    grpc.ssl_channel_credentials.assert_called_once_with(
        root_certificates=b"CERT"
    )
    grpc.secure_channel.assert_called_once_with("chirpstack:8080", credentials)


def test_create_tenant_returns_id_and_propagates(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Create.return_value = api.Tenant(id="tenant-id-1")
    monkeypatch.setattr(api, "TenantServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    tenant_id = client.create_tenant("Meu Tenant", "desc")

    assert tenant_id == "tenant-id-1"
    args, kwargs = fake_stub.Create.call_args
    assert args[0].tenant.name == "Meu Tenant"
    assert args[0].tenant.description == "desc"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_create_tenant_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Create.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "TenantServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.create_tenant("Meu Tenant", "desc")

    assert exc_info.value.operation == "create_tenant"
    assert exc_info.value.message == "device already exists"


def test_update_tenant_propagates_id_and_fields(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "TenantServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.update_tenant("tenant-id-1", "Nome Novo", "nova desc")

    args, kwargs = fake_stub.Update.call_args
    assert args[0].tenant.id == "tenant-id-1"
    assert args[0].tenant.name == "Nome Novo"
    assert args[0].tenant.description == "nova desc"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_delete_tenant_propagates_id(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "TenantServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.delete_tenant("tenant-id-1")

    args, kwargs = fake_stub.Delete.call_args
    assert args[0].id == "tenant-id-1"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_create_application_returns_id_and_propagates(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Create.return_value = api.Application(id="app-id-1")
    monkeypatch.setattr(
        api, "ApplicationServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    application_id = client.create_application("tenant-id-1", "Fazenda", "d")

    assert application_id == "app-id-1"
    args, kwargs = fake_stub.Create.call_args
    assert args[0].application.tenant_id == "tenant-id-1"
    assert args[0].application.name == "Fazenda"
    assert args[0].application.description == "d"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_create_application_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Create.side_effect = _FakeRpcError()
    monkeypatch.setattr(
        api, "ApplicationServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.create_application("tenant-id-1", "Fazenda", "d")

    assert exc_info.value.operation == "create_application"
    assert exc_info.value.message == "device already exists"


def test_update_application_propagates_id_and_fields(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(
        api, "ApplicationServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.update_application("app-id-1", "Fazenda Nova", "nova desc")

    args, kwargs = fake_stub.Update.call_args
    assert args[0].application.id == "app-id-1"
    assert args[0].application.name == "Fazenda Nova"
    assert args[0].application.description == "nova desc"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_delete_application_propagates_id(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(
        api, "ApplicationServiceStub", lambda channel: fake_stub
    )

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.delete_application("app-id-1")

    args, kwargs = fake_stub.Delete.call_args
    assert args[0].id == "app-id-1"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]
